"""
mcp_host/clients/postgres_client.py
─────────────────────────────────────
Client MCP pour le serveur PostgreSQL officiel.

Serveur : @modelcontextprotocol/server-postgres
Commande : npx -y @modelcontextprotocol/server-postgres <DATABASE_URL>

Outils exposés (par le serveur officiel) :
  - query          : Exécute une requête SQL SELECT
  - list_tables    : Liste les tables disponibles
  - describe_table : Décrit le schéma d'une table
"""

from __future__ import annotations

import os

from mcp.client.stdio import StdioServerParameters

from mcp_host.core.base_client import BaseMCPClient


class PostgresMCPClient(BaseMCPClient):
    """
    Client MCP pour PostgreSQL.

    Aucune logique métier — uniquement la configuration du sous-processus.
    La DATABASE_URL est lue depuis l'environnement.
    """

    @property
    def name(self) -> str:
        return "postgres"

    def server_params(self) -> StdioServerParameters:
        database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@db:5432/job_bot_general",
        )
        return StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres", database_url],
            env={
                **os.environ,
                "NODE_ENV": "production",
            },
        )
