"""
mcp_host/servers/registry.py
─────────────────────────────
Registre centralisé des serveurs MCP disponibles.

Responsabilités :
  - Centraliser les commandes de lancement de chaque serveur MCP
  - Valider la présence de `npx` et `uv` au démarrage
  - Fournir une factory pour instancier les clients correspondants
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_host.core.base_client import BaseMCPClient

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constantes — chemins filesystem accessibles au serveur
# ──────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/home/tor/Downloads/job-bot-general")

FILESYSTEM_ALLOWED_DIRS: list[str] = [
    PROJECT_ROOT,
    os.path.join(PROJECT_ROOT, "data"),
    os.path.join(PROJECT_ROOT, "output"),
    os.path.join(PROJECT_ROOT, "docs"),
]


# ──────────────────────────────────────────────────────────────────────────────
# Enum des serveurs disponibles
# ──────────────────────────────────────────────────────────────────────────────


class ServerID(str, Enum):
    POSTGRES = "postgres"
    FETCH = "fetch"
    FILESYSTEM = "filesystem"
    GITHUB = "github"
    SCRAPEGRAPH = "scrapegraph"


# ──────────────────────────────────────────────────────────────────────────────
# Descripteur de serveur
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ServerSpec:
    """Spécification immuable d'un serveur MCP."""

    id: ServerID
    command: str  # Exécutable principal (npx, uvx, python…)
    args: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)  # Noms des vars d'env requises
    description: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Registre
# ──────────────────────────────────────────────────────────────────────────────


class ServerRegistry:
    """
    Registre singleton des serveurs MCP.

    Usage :
        registry = ServerRegistry()
        registry.validate_dependencies()          # Vérifie npx + uv
        spec = registry.get(ServerID.POSTGRES)
        client = registry.build_client(ServerID.FETCH)
    """

    _SPECS: dict[ServerID, ServerSpec] = {
        ServerID.POSTGRES: ServerSpec(
            id=ServerID.POSTGRES,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres"],
            env_vars=["DATABASE_URL"],
            description="Serveur MCP PostgreSQL — accès SQL en lecture/écriture",
        ),
        ServerID.FETCH: ServerSpec(
            id=ServerID.FETCH,
            command="uvx",
            args=["mcp-server-fetch"],
            env_vars=[],
            description="Serveur MCP Fetch — récupération de pages web",
        ),
        ServerID.FILESYSTEM: ServerSpec(
            id=ServerID.FILESYSTEM,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"]
            + FILESYSTEM_ALLOWED_DIRS,
            env_vars=[],
            description="Serveur MCP Filesystem — accès lecture/écriture aux dossiers projet",
        ),
        ServerID.GITHUB: ServerSpec(
            id=ServerID.GITHUB,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env_vars=["GITHUB_PERSONAL_ACCESS_TOKEN"],
            description="Serveur MCP GitHub — API GitHub (repos, issues, PRs…)",
        ),
        ServerID.SCRAPEGRAPH: ServerSpec(
            id=ServerID.SCRAPEGRAPH,
            command="uvx",
            args=["scrapegraph-mcp@1.0.1"],
            env_vars=["SGAI_API_KEY"],
            description="Serveur MCP ScrapeGraph — scraping web intelligent",
        ),
    }

    def __init__(self) -> None:
        self._validated: bool = False

    # ──────────────────────────────────────────────────────────────────────────
    # Validation des dépendances système
    # ──────────────────────────────────────────────────────────────────────────

    def validate_dependencies(self) -> None:
        """
        Vérifie la présence de `npx` et `uv` dans le PATH.
        Lève RuntimeError si l'un des deux est absent.
        Doit être appelé au démarrage de l'application.
        """
        missing: list[str] = []

        for binary in ("npx", "uv"):
            path = shutil.which(binary)
            if path is None:
                missing.append(binary)
                logger.error(
                    "[Registry] Binaire manquant : '%s' introuvable dans PATH", binary
                )
            else:
                logger.info("[Registry] Binaire '%s' trouvé : %s", binary, path)

        if missing:
            raise RuntimeError(
                f"[Registry] Dépendances manquantes : {missing}. "
                "Installez Node.js (pour npx) et uv (pip install uv) avant de démarrer."
            )

        self._validated = True
        logger.info("[Registry] Toutes les dépendances système sont disponibles.")

    def validate_env_vars(self, server_id: ServerID) -> list[str]:
        """
        Retourne la liste des variables d'env manquantes pour un serveur donné.
        """
        spec = self.get(server_id)
        missing = [var for var in spec.env_vars if not os.environ.get(var)]
        if missing:
            logger.warning(
                "[Registry] Variables d'env manquantes pour '%s' : %s",
                server_id.value,
                missing,
            )
        return missing

    # ──────────────────────────────────────────────────────────────────────────
    # Accès aux specs
    # ──────────────────────────────────────────────────────────────────────────

    def get(self, server_id: ServerID) -> ServerSpec:
        """Retourne la spec d'un serveur par son ID."""
        if server_id not in self._SPECS:
            raise KeyError(f"[Registry] Serveur inconnu : '{server_id}'")
        return self._SPECS[server_id]

    def list_all(self) -> list[ServerSpec]:
        """Retourne toutes les specs enregistrées."""
        return list(self._SPECS.values())

    def describe(self) -> list[dict]:
        """Retourne une description JSON-serializable de tous les serveurs."""
        return [
            {
                "id": spec.id.value,
                "command": spec.command,
                "args": spec.args,
                "env_vars_required": spec.env_vars,
                "env_vars_present": [v for v in spec.env_vars if os.environ.get(v)],
                "description": spec.description,
            }
            for spec in self._SPECS.values()
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # Factory de clients
    # ──────────────────────────────────────────────────────────────────────────

    def build_client(self, server_id: ServerID) -> "BaseMCPClient":
        """
        Instancie et retourne le client MCP correspondant au serveur demandé.

        Import tardif pour éviter les dépendances circulaires.
        """
        # Import tardif intentionnel
        from mcp_host.clients.fetch_client import FetchMCPClient
        from mcp_host.clients.filesystem_client import FilesystemMCPClient
        from mcp_host.clients.github_client import GitHubMCPClient
        from mcp_host.clients.postgres_client import PostgresMCPClient
        from mcp_host.clients.scrapegraph_client import ScrapegraphMCPClient

        _factory: dict[ServerID, type] = {
            ServerID.POSTGRES: PostgresMCPClient,
            ServerID.FETCH: FetchMCPClient,
            ServerID.FILESYSTEM: FilesystemMCPClient,
            ServerID.GITHUB: GitHubMCPClient,
            ServerID.SCRAPEGRAPH: ScrapegraphMCPClient,
        }

        cls = _factory.get(server_id)
        if cls is None:
            raise KeyError(f"[Registry] Pas de client pour le serveur '{server_id}'")

        logger.debug("[Registry] Instanciation du client '%s'", server_id.value)
        return cls()


# ──────────────────────────────────────────────────────────────────────────────
# Instance globale
# ──────────────────────────────────────────────────────────────────────────────

registry = ServerRegistry()
