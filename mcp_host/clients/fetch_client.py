"""
mcp_host/clients/fetch_client.py
──────────────────────────────────
Client MCP pour le serveur Fetch officiel.

Serveur : mcp-server-fetch
Commande : uvx mcp-server-fetch

Outils exposés (par le serveur officiel) :
  - fetch : Récupère le contenu d'une URL (HTML, JSON, texte)
"""

from __future__ import annotations

import os

from mcp.client.stdio import StdioServerParameters

from mcp_host.core.base_client import BaseMCPClient


class FetchMCPClient(BaseMCPClient):
    """
    Client MCP pour la récupération de pages web via mcp-server-fetch.

    Aucune logique métier — uniquement la configuration du sous-processus.
    """

    @property
    def name(self) -> str:
        return "fetch"

    def server_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command="uvx",
            args=["mcp-server-fetch"],
            env={**os.environ},
        )
