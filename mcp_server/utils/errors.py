from __future__ import annotations


class MCPServerError(Exception):
    """Erreur de base de l'adaptateur MCP."""


class OrchestratorRequestError(MCPServerError):
    """Erreur lors d'un appel vers l'orchestrateur."""


class PayloadNormalizationError(MCPServerError):
    """Erreur lors de la normalisation d'un payload entrant ou sortant."""