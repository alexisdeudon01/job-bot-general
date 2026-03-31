"""
mcp_host/main.py
─────────────────
Orchestrateur / Host MCP — Point d'entrée unique.

Responsabilités :
  1. Valider les dépendances système (npx, uv) via le registre
  2. Instancier les clients MCP via la Factory (ServerRegistry)
  3. Collecter les outils disponibles de chaque serveur
  4. Gérer la boucle de dialogue avec OpenAI ou Anthropic :
       Envoi des outils → Réception de l'appel → Exécution locale → Retour du résultat
  5. Exposer une interface CLI simple pour tester le host

Usage :
    python -m mcp_host.main
    python -m mcp_host.main --provider openai --prompt "Liste les tables de la base"
    python -m mcp_host.main --list-tools
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

from mcp_host.servers.registry import ServerID, registry
from mcp_host.utils.translator import (
    extract_tool_result_text,
    tools_to_anthropic,
    tools_to_openai,
)

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("mcp_host")


# ──────────────────────────────────────────────────────────────────────────────
# Factory de clients
# ──────────────────────────────────────────────────────────────────────────────


def build_all_clients() -> dict[str, Any]:
    """
    Instancie tous les clients MCP disponibles via le registre.

    Retourne un dict { server_id_value → client_instance }.
    Les clients dont les variables d'env sont manquantes sont ignorés
    avec un avertissement (non bloquant).
    """
    clients: dict[str, Any] = {}

    for server_id in ServerID:
        missing_vars = registry.validate_env_vars(server_id)
        if missing_vars:
            logger.warning(
                "[Host] Client '%s' ignoré — variables manquantes : %s",
                server_id.value,
                missing_vars,
            )
            continue
        try:
            client = registry.build_client(server_id)
            clients[server_id.value] = client
            logger.info("[Host] Client '%s' instancié.", server_id.value)
        except Exception as exc:
            logger.error(
                "[Host] Impossible d'instancier '%s' : %s", server_id.value, exc
            )

    return clients


# ──────────────────────────────────────────────────────────────────────────────
# Collecte des outils
# ──────────────────────────────────────────────────────────────────────────────


async def collect_all_tools(clients: dict[str, Any]) -> dict[str, Any]:
    """
    Collecte les outils de tous les clients actifs.

    Retourne :
    {
        "raw":       { server_id → list[mcp.types.Tool] },
        "openai":    list[OpenAI tool dict],
        "anthropic": list[Anthropic tool dict],
        "index":     { tool_name → client_instance }   ← pour le dispatch
    }
    """
    raw: dict[str, list[Any]] = {}
    openai_tools: list[dict[str, Any]] = []
    anthropic_tools: list[dict[str, Any]] = []
    tool_index: dict[str, Any] = {}

    for server_id, client in clients.items():
        try:
            tools = await client.list_tools()
            raw[server_id] = tools
            openai_tools.extend(tools_to_openai(tools))
            anthropic_tools.extend(tools_to_anthropic(tools))
            for tool in tools:
                tool_index[tool.name] = client
            logger.info(
                "[Host] '%s' → %d outil(s) : %s",
                server_id,
                len(tools),
                [t.name for t in tools],
            )
        except Exception as exc:
            logger.error("[Host] Erreur collecte outils '%s' : %s", server_id, exc)

    return {
        "raw": raw,
        "openai": openai_tools,
        "anthropic": anthropic_tools,
        "index": tool_index,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Boucle de dialogue OpenAI
# ──────────────────────────────────────────────────────────────────────────────


async def run_openai_loop(
    prompt: str,
    tool_index: dict[str, Any],
    openai_tools: list[dict[str, Any]],
    model: str = "gpt-4o",
) -> str:
    """
    Boucle de dialogue avec OpenAI (function calling).

    1. Envoie le prompt + les outils disponibles
    2. Si OpenAI appelle un outil → exécute via le client MCP correspondant
    3. Renvoie le résultat à OpenAI
    4. Répète jusqu'à une réponse finale (finish_reason = "stop")
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai package requis : pip install openai")

    oai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # On utilise Any pour éviter les conflits de typage strict du SDK OpenAI
    messages: list[Any] = [{"role": "user", "content": prompt}]

    logger.info("[Host/OpenAI] Démarrage boucle avec modèle '%s'", model)

    while True:
        create_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if openai_tools:
            create_kwargs["tools"] = openai_tools
            create_kwargs["tool_choice"] = "auto"

        response = await oai_client.chat.completions.create(**create_kwargs)  # type: ignore[arg-type]

        choice = response.choices[0]
        message = choice.message
        messages.append(message.model_dump(exclude_none=True))

        if choice.finish_reason == "stop" or not message.tool_calls:
            logger.info("[Host/OpenAI] Réponse finale reçue.")
            return message.content or ""

        # Exécution des appels d'outils
        for tool_call in message.tool_calls:
            # Accès défensif pour compatibilité avec tous les types de tool_call
            fn = getattr(tool_call, "function", None)
            if fn is None:
                continue
            tool_name: str = getattr(fn, "name", "")
            raw_args: str = getattr(fn, "arguments", "{}") or "{}"
            tool_args: dict[str, Any] = json.loads(raw_args)

            logger.info("[Host/OpenAI] Appel outil '%s' args=%s", tool_name, tool_args)

            mcp_client = tool_index.get(tool_name)
            if mcp_client is None:
                tool_result = (
                    f"Erreur : outil '{tool_name}' introuvable dans le registre."
                )
            else:
                try:
                    content = await mcp_client.call_tool(tool_name, tool_args)
                    tool_result = extract_tool_result_text(content)
                except Exception as exc:
                    tool_result = f"Erreur lors de l'exécution de '{tool_name}' : {exc}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )


# ──────────────────────────────────────────────────────────────────────────────
# Boucle de dialogue Anthropic
# ──────────────────────────────────────────────────────────────────────────────


async def run_anthropic_loop(
    prompt: str,
    tool_index: dict[str, Any],
    anthropic_tools: list[dict[str, Any]],
    model: str = "claude-3-5-sonnet-20241022",
) -> str:
    """
    Boucle de dialogue avec Anthropic (tool use).

    1. Envoie le prompt + les outils disponibles
    2. Si Anthropic appelle un outil → exécute via le client MCP correspondant
    3. Renvoie le résultat à Anthropic
    4. Répète jusqu'à une réponse finale (stop_reason = "end_turn")
    """
    try:
        import anthropic as anthropic_sdk
    except ImportError:
        raise RuntimeError("anthropic package requis : pip install anthropic")

    ant_client = anthropic_sdk.AsyncAnthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )

    # On utilise Any pour éviter les conflits de typage strict du SDK Anthropic
    messages: list[Any] = [{"role": "user", "content": prompt}]

    logger.info("[Host/Anthropic] Démarrage boucle avec modèle '%s'", model)

    while True:
        response = await ant_client.messages.create(  # type: ignore[call-overload]
            model=model,
            max_tokens=4096,
            messages=messages,
            tools=anthropic_tools,  # type: ignore[arg-type]
        )

        # Ajoute la réponse de l'assistant
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extrait le texte de la réponse finale (TextBlock uniquement)
            for block in response.content:
                # Vérification par attribut pour compatibilité multi-versions SDK
                if getattr(block, "type", None) == "text":
                    return str(getattr(block, "text", ""))
            return ""

        if response.stop_reason != "tool_use":
            logger.warning(
                "[Host/Anthropic] stop_reason inattendu : %s", response.stop_reason
            )
            break

        # Exécution des appels d'outils (ToolUseBlock uniquement)
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            tool_name: str = getattr(block, "name", "")
            raw_input: Any = getattr(block, "input", {})
            tool_args: dict[str, Any] = dict(raw_input) if raw_input else {}

            logger.info(
                "[Host/Anthropic] Appel outil '%s' args=%s", tool_name, tool_args
            )

            mcp_client = tool_index.get(tool_name)
            if mcp_client is None:
                tool_result_text = (
                    f"Erreur : outil '{tool_name}' introuvable dans le registre."
                )
            else:
                try:
                    content = await mcp_client.call_tool(tool_name, tool_args)
                    tool_result_text = extract_tool_result_text(content)
                except Exception as exc:
                    tool_result_text = (
                        f"Erreur lors de l'exécution de '{tool_name}' : {exc}"
                    )

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": getattr(block, "id", ""),
                    "content": tool_result_text,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ──────────────────────────────────────────────────────────────────────────────


async def main(args: argparse.Namespace) -> None:
    """Fonction principale asynchrone."""

    # 1. Validation des dépendances système
    logger.info("[Host] Validation des dépendances système...")
    try:
        registry.validate_dependencies()
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    # 2. Instanciation des clients via Factory
    logger.info("[Host] Instanciation des clients MCP...")
    clients = build_all_clients()

    if not clients:
        logger.error(
            "[Host] Aucun client MCP disponible. Vérifiez vos variables d'env."
        )
        sys.exit(1)

    # 3. Collecte des outils
    logger.info("[Host] Collecte des outils disponibles...")
    tools_data = await collect_all_tools(clients)

    # Mode --list-tools : affiche les outils et quitte
    if args.list_tools:
        print("\n=== Outils MCP disponibles ===\n")
        for server_id, tools in tools_data["raw"].items():
            print(f"[{server_id}]")
            for tool in tools:
                print(f"  • {tool.name}: {tool.description or '(pas de description)'}")
        print(f"\nTotal : {len(tools_data['index'])} outil(s)\n")
        return

    # Mode --list-registry : affiche le registre et quitte
    if args.list_registry:
        print("\n=== Registre des serveurs MCP ===\n")
        print(json.dumps(registry.describe(), indent=2, ensure_ascii=False))
        return

    # 4. Boucle de dialogue
    if not args.prompt:
        logger.error("[Host] --prompt requis pour lancer une conversation.")
        sys.exit(1)

    provider = args.provider.lower()
    logger.info("[Host] Lancement boucle dialogue — provider='%s'", provider)

    if provider == "openai":
        result = await run_openai_loop(
            prompt=args.prompt,
            tool_index=tools_data["index"],
            openai_tools=tools_data["openai"],
            model=args.model or "gpt-4o",
        )
    elif provider == "anthropic":
        result = await run_anthropic_loop(
            prompt=args.prompt,
            tool_index=tools_data["index"],
            anthropic_tools=tools_data["anthropic"],
            model=args.model or "claude-3-5-sonnet-20241022",
        )
    else:
        logger.error(
            "[Host] Provider inconnu : '%s'. Utilisez 'openai' ou 'anthropic'.",
            provider,
        )
        sys.exit(1)

    print("\n=== Réponse ===\n")
    print(result)
    print()


def cli() -> None:
    """Interface CLI."""
    parser = argparse.ArgumentParser(
        description="MCP Host — Orchestrateur de clients MCP avec OpenAI/Anthropic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python -m mcp_host.main --list-tools
  python -m mcp_host.main --list-registry
  python -m mcp_host.main --provider openai --prompt "Liste les tables de la base"
  python -m mcp_host.main --provider anthropic --prompt "Scrape https://example.com"
        """,
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic"],
        default="openai",
        help="Fournisseur LLM à utiliser (défaut: openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Modèle LLM (défaut: gpt-4o pour OpenAI, claude-3-5-sonnet pour Anthropic)",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Prompt utilisateur à envoyer au LLM",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Affiche tous les outils MCP disponibles et quitte",
    )
    parser.add_argument(
        "--list-registry",
        action="store_true",
        help="Affiche le registre des serveurs MCP et quitte",
    )

    args = parser.parse_args()
    asyncio.run(main(args))


if __name__ == "__main__":
    cli()
