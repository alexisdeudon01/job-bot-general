from __future__ import annotations

import json
import os

import requests

from mcp_server.utils.errors import OrchestratorRequestError


class OrchestratorClient:
    """Client HTTP minimal vers l'orchestrateur API-first."""

    def __init__(self, base_url: str | None = None, timeout_seconds: int = 120):
        self.base_url = (base_url or os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise OrchestratorRequestError(f"Failed to call orchestrator: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise OrchestratorRequestError("Invalid JSON response from orchestrator") from exc