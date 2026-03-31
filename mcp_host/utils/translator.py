"""
mcp_host/utils/translator.py
──────────────────────────────
Convertisseur de définitions d'outils MCP vers les formats JSON Schema
attendus par OpenAI et Anthropic.

MCP Tool → OpenAI function calling format
MCP Tool → Anthropic tool use format

Référence :
  - OpenAI  : https://platform.openai.com/docs/guides/function-calling
  - Anthropic: https://docs.anthropic.com/en/docs/tool-use
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI
# ──────────────────────────────────────────────────────────────────────────────


def tool_to_openai(tool: Tool) -> dict[str, Any]:
    """
    Convertit un outil MCP au format OpenAI function calling.

    Format cible :
    {
        "type": "function",
        "function": {
            "name": "...",
            "description": "...",
            "parameters": { <JSON Schema> }
        }
    }
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": _normalize_input_schema(tool.inputSchema),
        },
    }


def tools_to_openai(tools: list[Tool]) -> list[dict[str, Any]]:
    """Convertit une liste d'outils MCP au format OpenAI."""
    return [tool_to_openai(t) for t in tools]


# ──────────────────────────────────────────────────────────────────────────────
# Anthropic
# ──────────────────────────────────────────────────────────────────────────────


def tool_to_anthropic(tool: Tool) -> dict[str, Any]:
    """
    Convertit un outil MCP au format Anthropic tool use.

    Format cible :
    {
        "name": "...",
        "description": "...",
        "input_schema": { <JSON Schema> }
    }
    """
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": _normalize_input_schema(tool.inputSchema),
    }


def tools_to_anthropic(tools: list[Tool]) -> list[dict[str, Any]]:
    """Convertit une liste d'outils MCP au format Anthropic."""
    return [tool_to_anthropic(t) for t in tools]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ──────────────────────────────────────────────────────────────────────────────


def _normalize_input_schema(schema: Any) -> dict[str, Any]:
    """
    Normalise le inputSchema MCP en JSON Schema standard.

    - Si le schéma est None ou vide → retourne un objet vide valide
    - Si le schéma est un dict → le retourne tel quel (déjà JSON Schema)
    - Sinon → tente une conversion best-effort
    """
    if schema is None:
        return {"type": "object", "properties": {}}

    if isinstance(schema, dict):
        # S'assure que "type" est présent
        if "type" not in schema:
            schema = {"type": "object", **schema}
        return schema

    # Fallback : schéma Pydantic ou autre objet avec .model_json_schema()
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()

    # Dernier recours
    return {"type": "object", "properties": {}}


# ──────────────────────────────────────────────────────────────────────────────
# Utilitaire : extraction du résultat d'un appel d'outil MCP
# ──────────────────────────────────────────────────────────────────────────────


def extract_tool_result_text(content: list[Any]) -> str:
    """
    Extrait le texte brut d'une réponse MCP (liste de TextContent / ImageContent).

    Retourne une chaîne vide si aucun contenu textuel n'est trouvé.
    """
    parts: list[str] = []
    for item in content:
        # mcp.types.TextContent
        if hasattr(item, "text"):
            parts.append(item.text)
        # dict fallback
        elif isinstance(item, dict) and "text" in item:
            parts.append(item["text"])
    return "\n".join(parts)
