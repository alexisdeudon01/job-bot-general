from __future__ import annotations

from typing import Any

from dashboard.utils.formatters import format_datetime, format_number, format_status_label


def build_overview_metrics(overview: dict[str, Any]) -> list[dict[str, str]]:
    metrics = overview.get("metrics", [])
    if metrics:
        return [
            {
                "label": str(metric.get("label", metric.get("key", "Metric"))),
                "value": format_number(metric.get("value", 0)),
                "delta": str(metric.get("trend") or ""),
            }
            for metric in metrics
        ]

    return [
        {"label": "Organisations", "value": "0", "delta": ""},
        {"label": "Offres", "value": "0", "delta": ""},
        {"label": "Candidatures", "value": "0", "delta": ""},
        {"label": "Runs pipeline", "value": "0", "delta": ""},
    ]


def build_pipeline_timeline_text(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "Aucun run pipeline disponible."

    lines = []
    for run in runs[:8]:
        run_id = run.get("id") or run.get("run_id") or "?"
        status = format_status_label(run.get("status"))
        started_at = format_datetime(run.get("started_at") or run.get("created_at"))
        lines.append(f"• Run #{run_id} — {status} — {started_at}")
    return "\n".join(lines)


def build_status_distribution(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        status = format_status_label(item.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return [{"status": key, "count": value} for key, value in counts.items()]


def build_provider_cards(data: Any) -> list[dict[str, str]]:
    items = data if isinstance(data, list) else data.get("items", [])
    cards = []
    for item in items:
        cards.append(
            {
                "name": str(item.get("name", "provider")),
                "status": format_status_label(item.get("status")),
                "detail": str(item.get("detail") or item.get("message") or "Aucun détail"),
            }
        )
    return cards


def build_runs_table(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("runs", data.get("items", []))
    rows = []
    for item in items:
        rows.append(
            {
                "id": item.get("id") or item.get("run_id"),
                "service": item.get("service_name") or item.get("service") or "pipeline",
                "status": format_status_label(item.get("status")),
                "started_at": format_datetime(item.get("started_at") or item.get("created_at")),
                "finished_at": format_datetime(item.get("finished_at") or item.get("updated_at")),
            }
        )
    return rows


def build_entities_table(overview: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = overview.get("metrics", [])
    if metrics:
        return [
            {
                "entity": str(metric.get("label", metric.get("key", "Entité"))),
                "count": metric.get("value", 0),
            }
            for metric in metrics
        ]

    return []


def build_github_runs_table(data: Any) -> list[dict[str, Any]]:
    items = data if isinstance(data, list) else data.get("items", [])
    rows = []
    for item in items:
        rows.append(
            {
                "workflow": item.get("workflow_name") or item.get("name") or "workflow",
                "status": format_status_label(item.get("status") or item.get("conclusion")),
                "branch": item.get("branch") or item.get("head_branch") or "—",
                "started_at": format_datetime(item.get("started_at") or item.get("created_at")),
            }
        )
    return rows


def build_llm_history_rows(overview: dict[str, Any], providers: Any) -> list[dict[str, Any]]:
    rows = []
    generated_at = format_datetime(overview.get("generated_at"))
    items = providers if isinstance(providers, list) else providers.get("items", [])
    for item in items:
        rows.append(
            {
                "provider": item.get("name", "provider"),
                "status": format_status_label(item.get("status")),
                "last_seen": generated_at,
                "detail": item.get("detail") or item.get("message") or "Statut agrégé depuis l'API",
            }
        )
    return rows
