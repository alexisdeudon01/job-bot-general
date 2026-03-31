"""
mcp_host/core/base_client.py
────────────────────────────
Classe de base abstraite pour tous les clients MCP stdio.

Utilise exclusivement le SDK officiel :
  - mcp.ClientSession
  - mcp.client.stdio.stdio_client

Gère :
  - Cycle de vie stdio (connect / session / disconnect)
  - Logs JSON-RPC structurés
  - Reconnexion automatique si le sous-processus crash
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import Tool

logger = logging.getLogger(__name__)


class BaseMCPClient(ABC):
    """
    Classe de base pour tous les clients MCP stdio.

    Sous-classes doivent implémenter :
      - server_params() → StdioServerParameters
      - name (property str)
    """

    # Nombre maximum de tentatives de reconnexion automatique
    MAX_RECONNECT_ATTEMPTS: int = 3
    RECONNECT_DELAY_SECONDS: float = 2.0

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._tools_cache: list[Tool] | None = None
        self._reconnect_attempts: int = 0

    # ──────────────────────────────────────────────────────────────────────────
    # Interface abstraite
    # ──────────────────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifiant lisible du client (ex: 'postgres', 'fetch')."""

    @abstractmethod
    def server_params(self) -> StdioServerParameters:
        """
        Retourne les paramètres de lancement du sous-processus MCP.
        Exemple :
            return StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-postgres", DATABASE_URL],
                env={"NODE_ENV": "production"},
            )
        """

    # ──────────────────────────────────────────────────────────────────────────
    # Cycle de vie
    # ──────────────────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        """
        Context manager qui ouvre une session MCP stdio et la ferme proprement.

        Usage :
            async with client.session() as sess:
                tools = await sess.list_tools()
        """
        params = self.server_params()
        logger.info(
            "[MCP:%s] Démarrage du sous-processus : %s %s",
            self.name,
            params.command,
            " ".join(params.args or []),
        )

        attempt = 0
        last_exc: Exception | None = None

        while attempt <= self.MAX_RECONNECT_ATTEMPTS:
            try:
                async with stdio_client(params) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as sess:
                        await sess.initialize()
                        logger.info(
                            "[MCP:%s] Session initialisée avec succès.", self.name
                        )
                        self._reconnect_attempts = 0
                        yield sess
                        return  # sortie normale
            except Exception as exc:
                last_exc = exc
                attempt += 1
                if attempt > self.MAX_RECONNECT_ATTEMPTS:
                    break
                logger.warning(
                    "[MCP:%s] Erreur de session (tentative %d/%d) : %s — reconnexion dans %.1fs",
                    self.name,
                    attempt,
                    self.MAX_RECONNECT_ATTEMPTS,
                    exc,
                    self.RECONNECT_DELAY_SECONDS,
                )
                await asyncio.sleep(self.RECONNECT_DELAY_SECONDS)

        logger.error(
            "[MCP:%s] Échec après %d tentatives : %s",
            self.name,
            self.MAX_RECONNECT_ATTEMPTS,
            last_exc,
        )
        raise RuntimeError(
            f"[MCP:{self.name}] Impossible d'établir la session après "
            f"{self.MAX_RECONNECT_ATTEMPTS} tentatives : {last_exc}"
        ) from last_exc

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers publics
    # ──────────────────────────────────────────────────────────────────────────

    async def list_tools(self) -> list[Tool]:
        """Liste les outils exposés par ce serveur MCP (avec cache en mémoire)."""
        if self._tools_cache is not None:
            return self._tools_cache

        async with self.session() as sess:
            result = await sess.list_tools()
            self._tools_cache = result.tools
            logger.debug(
                "[MCP:%s] %d outil(s) disponible(s) : %s",
                self.name,
                len(self._tools_cache),
                [t.name for t in self._tools_cache],
            )
            return self._tools_cache

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> Any:
        """
        Appelle un outil MCP et retourne le résultat brut.

        Args:
            tool_name:  Nom de l'outil tel qu'exposé par le serveur.
            arguments:  Dictionnaire d'arguments (optionnel).

        Returns:
            Contenu de la réponse MCP (liste de TextContent / ImageContent / etc.)
        """
        args = arguments or {}
        logger.info(
            "[MCP:%s] Appel outil '%s' avec args=%s", self.name, tool_name, args
        )

        async with self.session() as sess:
            response = await sess.call_tool(tool_name, args)
            logger.debug(
                "[MCP:%s] Réponse outil '%s' : %s", self.name, tool_name, response
            )
            return response.content

    def invalidate_tools_cache(self) -> None:
        """Invalide le cache des outils (utile après reconnexion)."""
        self._tools_cache = None
        logger.debug("[MCP:%s] Cache outils invalidé.", self.name)
