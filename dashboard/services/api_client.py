from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any

from dashboard.services.api_routes import ROUTES

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency during refactors
    httpx = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


DEFAULT_API_BASE_URL = os.getenv("DASHBOARD_API_BASE_URL", "http://localhost:8000")


class ApiClient:
    """Thin route-driven dashboard API client with minimal fallback support."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or DEFAULT_API_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._overview_cache: dict[str, Any] | None = None

    def is_available(self) -> bool:
        return httpx is not None

    def build_url(self, path: str) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{clean_path}"

    def _clone_fallback(self, fallback: Any) -> Any:
        if fallback is None:
            return None
        return deepcopy(fallback)

    def _request_json(self, path: str, fallback: Any = None) -> Any:
        fallback_payload = self._clone_fallback(fallback)
        if httpx is None:
            return fallback_payload

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.build_url(path))
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Failed to fetch dashboard API path %s: %s", path, exc)
            return fallback_payload

    def post_json(self, path: str, payload: Any = None, fallback: Any = None) -> Any:
        """POST JSON payload to the given path and return the parsed response."""
        fallback_payload = self._clone_fallback(fallback)
        if httpx is None:
            return fallback_payload

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.build_url(path), json=payload)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Failed to POST to dashboard API path %s: %s", path, exc)
            return fallback_payload

    def fetch_health(self) -> dict[str, Any]:
        fallback = {"status": "unreachable", "source": "fallback"}
        return self._request_json(ROUTES.health, fallback=fallback) or deepcopy(
            fallback
        )

    def fetch_dashboard_overview(self) -> dict[str, Any]:
        if self._overview_cache is not None:
            return deepcopy(self._overview_cache)

        fallback = {
            "metrics": [],
            "services": [],
            "recent_pipeline_runs": [],
            "recent_github_runs": [],
            "source": "fallback",
        }
        data = self._request_json(ROUTES.overview, fallback=fallback) or deepcopy(
            fallback
        )
        self._overview_cache = deepcopy(data)
        return data

    def fetch_pipeline_runs(self) -> dict[str, Any]:
        fallback = {"runs": [], "total": 0, "source": "fallback"}
        return self._request_json(ROUTES.pipeline_runs, fallback=fallback) or deepcopy(
            fallback
        )

    def fetch_provider_status(self) -> list[dict[str, Any]]:
        fallback: list[dict[str, Any]] = []
        return self._request_json(ROUTES.provider_status, fallback=fallback) or []

    def fetch_github_actions_runs(self) -> list[dict[str, Any]] | dict[str, Any]:
        fallback: list[dict[str, Any]] = []
        return self._request_json(ROUTES.github_actions_runs, fallback=fallback) or []

    def fetch_dashboard_entities(self) -> dict[str, Any]:
        fallback = {
            "summary": [],
            "relationships": [],
            "records": {},
            "source": "fallback",
        }
        return self._request_json(ROUTES.entities, fallback=fallback) or deepcopy(
            fallback
        )

    def fetch_dashboard_llm_history(self) -> dict[str, Any]:
        fallback = {
            "summary": [],
            "recent_messages": [],
            "sessions": [],
            "source": "fallback",
        }
        return self._request_json(ROUTES.llm_history, fallback=fallback) or deepcopy(
            fallback
        )

    def fetch_dashboard_mcp(self) -> dict[str, Any]:
        fallback = {"summary": [], "servers": [], "tools": [], "source": "fallback"}
        return self._request_json(ROUTES.mcp_status, fallback=fallback) or deepcopy(
            fallback
        )

    def fetch_dashboard_db_graph(self) -> dict[str, Any]:
        fallback = {"nodes": [], "edges": [], "diagram": "", "source": "fallback"}
        return self._request_json(ROUTES.db_schema, fallback=fallback) or deepcopy(
            fallback
        )
