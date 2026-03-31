"""
mcp_host/clients/filesystem_client.py
───────────────────────────────────────
Client MCP pour le serveur Filesystem officiel.

Serveur : @modelcontextprotocol/server-filesystem
Commande : npx -y @modelcontextprotocol/server-filesystem <dir1> <dir2> ...

Outils exposés (par le serveur officiel) :
  - read_file          : Lit le contenu d'un fichier
  - write_file         : Écrit dans un fichier
  - list_directory     : Liste le contenu d'un répertoire
  - create_directory   : Crée un répertoire
  - move_file          : Déplace / renomme un fichier
  - search_files       : Recherche des fichiers par pattern
  - get_file_info      : Métadonnées d'un fichier
  - list_allowed_directories : Liste les répertoires autorisés
"""

from __future__ import annotations

import os

from mcp.client.stdio import StdioServerParameters

from mcp_host.core.base_client import BaseMCPClient
from mcp_host.servers.registry import FILESYSTEM_ALLOWED_DIRS


class FilesystemMCPClient(BaseMCPClient):
    """
    Client MCP pour l'accès au système de fichiers du projet.

    Les répertoires autorisés sont définis dans registry.FILESYSTEM_ALLOWED_DIRS.
    Aucune logique métier — uniquement la configuration du sous-processus.
    """

    @property
    def name(self) -> str:
        return "filesystem"

    def server_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"]
            + FILESYSTEM_ALLOWED_DIRS,
            env={
                **os.environ,
                "NODE_ENV": "production",
            },
        )
