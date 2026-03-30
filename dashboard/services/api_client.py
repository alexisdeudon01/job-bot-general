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
            "entities": {
                "summary": [],
                "relationships": [],
                "records": {},
            },
            "llm_history": {
                "summary": [],
                "recent_messages": [],
                "sessions": [],
            },
            "mcp": {
                "summary": [],
                "servers": [],
                "tools": [],
            },
            "db_graph": {
                "nodes": [],
                "edges": [],
                "diagram": "",
            },
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
<<<<<<< HEAD
=======
<<<<<<< Updated upstream
=======
>>>>>>> 95144aa (kj)

    def fetch_dashboard_entities(self) -> dict[str, Any]:
        fallback = self.fetch_dashboard_overview().get("entities") or {
            "summary": [],
            "relationships": [],
            "records": {},
            "source": "overview_fallback",
        }
        return self.get_json("/api/v1/dashboard/entities", fallback=fallback) or fallback

    def fetch_dashboard_llm_history(self) -> dict[str, Any]:
        fallback = self.fetch_dashboard_overview().get("llm_history") or {
            "summary": [],
            "recent_messages": [],
            "sessions": [],
            "source": "overview_fallback",
        }
        return self.get_json("/api/v1/dashboard/llm-history", fallback=fallback) or fallback

    def fetch_dashboard_mcp(self) -> dict[str, Any]:
        fallback = self.fetch_dashboard_overview().get("mcp") or {
            "summary": [],
            "servers": [],
            "tools": [],
            "source": "overview_fallback",
        }
<<<<<<< HEAD
        return self.get_json("/api/v1/dashboard/mcp", fallback=fallback) or fallback
=======
        return self.get_json("/api/v1/dashboard/mcp-status", fallback=fallback) or fallback
>>>>>>> 95144aa (kj)

    def fetch_dashboard_db_graph(self) -> dict[str, Any]:
        fallback = self.fetch_dashboard_overview().get("db_graph") or {
            "nodes": [],
            "edges": [],
            "diagram": "",
            "source": "overview_fallback",
        }
<<<<<<< HEAD
        return self.get_json("/api/v1/dashboard/db-graph", fallback=fallback) or fallback
=======
        return self.get_json("/api/v1/dashboard/db-schema", fallback=fallback) or fallback
>>>>>>> Stashed changes
>>>>>>> 95144aa (kj)
