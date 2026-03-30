from __future__ import annotations

import os
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover - dépendance optionnelle en phase de refonte
    httpx = None  # type: ignore[assignment]


DEFAULT_API_BASE_URL = os.getenv("DASHBOARD_API_BASE_URL", "http://localhost:8000")


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or DEFAULT_API_BASE_URL).rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        return httpx is not None

    def build_url(self, path: str) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{clean_path}"

    def get_json(self, path: str, fallback: Any = None) -> Any:
        if httpx is None:
            return fallback

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.build_url(path))
                response.raise_for_status()
                return response.json()
        except Exception:
            return fallback

    def post_json(self, path: str, payload: dict[str, Any] | None = None, fallback: Any = None) -> Any:
        if httpx is None:
            return fallback

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.build_url(path), json=payload or {})
                response.raise_for_status()
                return response.json()
        except Exception:
            return fallback

    def fetch_health(self) -> dict[str, Any]:
        return self.get_json("/health", fallback={"status": "unreachable", "source": "fallback"}) or {}

    def fetch_dashboard_overview(self) -> dict[str, Any]:
        fallback = {
            "generated_at": None,
            "status": "fallback",
            "metrics": [
                {"key": "organizations", "label": "Organisations", "value": 0},
                {"key": "job_posts", "label": "Offres", "value": 0},
                {"key": "applications", "label": "Candidatures", "value": 0},
                {"key": "pipeline_runs", "label": "Runs pipeline", "value": 0},
            ],
            "services": [],
            "recent_pipeline_runs": [],
            "recent_github_runs": [],
            "source": "fallback",
        }
        return self.get_json("/api/v1/dashboard/overview", fallback=fallback) or fallback

    def fetch_pipeline_runs(self) -> dict[str, Any]:
        fallback = {"runs": [], "total": 0, "source": "fallback"}
        return self.get_json("/api/v1/pipeline/runs", fallback=fallback) or fallback

    def fetch_provider_status(self) -> list[dict[str, Any]]:
        fallback: list[dict[str, Any]] = []
        return self.get_json("/api/v1/providers/status", fallback=fallback) or fallback

    def fetch_github_actions_runs(self) -> list[dict[str, Any]]:
        fallback: list[dict[str, Any]] = []
        return self.get_json("/api/v1/github-actions/runs", fallback=fallback) or fallback
