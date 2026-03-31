"""
mcp_host/clients/scrapegraph_client.py
────────────────────────────────────────
Client MCP pour le serveur ScrapeGraph officiel.

Serveur : scrapegraph-mcp@1.0.1
Commande : uvx scrapegraph-mcp@1.0.1

Variable d'env requise : SGAI_API_KEY

Outils exposés (par le serveur officiel) :
  - markdownify        : Convertit une page web en Markdown structuré
  - smartscraper       : Extraction structurée via prompt naturel
  - searchscraper      : Recherche web + extraction multi-sources
  - scrape             : Récupération brute avec rendu JS optionnel
  - sitemap            : Extraction de la sitemap d'un site
  - smartcrawler_*     : Crawling multi-pages asynchrone
  - agentic_scrapper   : Workflow de scraping avancé
"""

from __future__ import annotations

import os

from mcp.client.stdio import StdioServerParameters

from mcp_host.core.base_client import BaseMCPClient


class ScrapegraphMCPClient(BaseMCPClient):
    """
    Client MCP pour ScrapeGraph AI.

    La clé API est lue depuis SGAI_API_KEY.
    Aucune logique métier — uniquement la configuration du sous-processus.
    """

    @property
    def name(self) -> str:
        return "scrapegraph"

    def server_params(self) -> StdioServerParameters:
        sgai_api_key = os.environ.get("SGAI_API_KEY", "")

        return StdioServerParameters(
            command="uvx",
            args=["scrapegraph-mcp@1.0.1"],
            env={
                **os.environ,
                "SGAI_API_KEY": sgai_api_key,
            },
        )
