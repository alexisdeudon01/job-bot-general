"""
mcp_host/clients/github_client.py
───────────────────────────────────
Client MCP pour le serveur GitHub officiel.

Serveur : @modelcontextprotocol/server-github
Commande : npx -y @modelcontextprotocol/server-github

Variable d'env requise : GITHUB_PERSONAL_ACCESS_TOKEN (mappée depuis GH_TOKEN)

Outils exposés (par le serveur officiel) :
  - create_or_update_file   : Crée ou met à jour un fichier dans un repo
  - search_repositories     : Recherche des dépôts GitHub
  - create_repository       : Crée un nouveau dépôt
  - get_file_contents       : Lit le contenu d'un fichier dans un repo
  - push_files              : Pousse plusieurs fichiers en un commit
  - create_issue            : Crée une issue
  - create_pull_request     : Crée une pull request
  - fork_repository         : Fork un dépôt
  - create_branch           : Crée une branche
  - list_commits            : Liste les commits d'une branche
  - list_issues             : Liste les issues d'un repo
  - update_issue            : Met à jour une issue
  - add_issue_comment       : Ajoute un commentaire à une issue
  - search_code             : Recherche du code dans GitHub
  - search_issues           : Recherche des issues/PRs
  - search_users            : Recherche des utilisateurs
  - get_issue               : Récupère une issue spécifique
  - get_pull_request        : Récupère une PR spécifique
  - list_pull_requests      : Liste les PRs d'un repo
"""

from __future__ import annotations

import os

from mcp.client.stdio import StdioServerParameters

from mcp_host.core.base_client import BaseMCPClient


class GitHubMCPClient(BaseMCPClient):
    """
    Client MCP pour l'API GitHub.

    Le token est lu depuis GH_TOKEN (alias GITHUB_PERSONAL_ACCESS_TOKEN).
    Aucune logique métier — uniquement la configuration du sous-processus.
    """

    @property
    def name(self) -> str:
        return "github"

    def server_params(self) -> StdioServerParameters:
        # Le serveur officiel attend GITHUB_PERSONAL_ACCESS_TOKEN
        gh_token = os.environ.get("GH_TOKEN") or os.environ.get(
            "GITHUB_PERSONAL_ACCESS_TOKEN", ""
        )

        return StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={
                **os.environ,
                "GITHUB_PERSONAL_ACCESS_TOKEN": gh_token,
                "NODE_ENV": "production",
            },
        )
