from __future__ import annotations

from typing import Any

from utils.formatters import format_datetime, format_number, format_status_label


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
    entity_payload = overview.get("entities") if isinstance(overview, dict) else {}
    summary = entity_payload.get("summary", []) if isinstance(entity_payload, dict) else []
    if summary:
        rows = []
        for item in summary:
            rows.append(
                {
                    "entity": str(item.get("entity") or item.get("name") or item.get("label") or "Entité"),
                    "count": item.get("count", item.get("value", 0)),
                    "description": str(item.get("description") or item.get("detail") or "—"),
                    "last_updated": format_datetime(item.get("last_updated") or item.get("updated_at")),
                }
            )
        return rows

    metrics = overview.get("metrics", [])
    if metrics:
        return [
            {
                "entity": str(metric.get("label", metric.get("key", "Entité"))),
                "count": metric.get("value", 0),
                "description": "Agrégat issu de overview",
                "last_updated": "—",
            }
            for metric in metrics
        ]

    return []


def build_entity_relationship_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    relationships = payload.get("relationships", [])
    rows = []
    for item in relationships:
        rows.append(
            {
                "source": item.get("source") or item.get("from") or "—",
                "target": item.get("target") or item.get("to") or "—",
                "relation": item.get("relation") or item.get("type") or "linked_to",
                "count": item.get("count", "—"),
            }
        )
    return rows


def build_entity_record_sections(payload: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    records = payload.get("records", {})
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    if isinstance(records, dict):
        for key, items in records.items():
            if isinstance(items, list):
                sections.append((str(key), items))
    return sections


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
    llm_payload = overview if overview.get("summary") is not None or overview.get("recent_messages") is not None else {}
    summary = llm_payload.get("summary", [])
    if summary:
        rows = []
        for item in summary:
            rows.append(
                {
                    "provider": item.get("provider", item.get("name", "provider")),
                    "model": item.get("model") or item.get("model_name") or "—",
                    "status": format_status_label(item.get("status")),
                    "requests": item.get("requests", item.get("count", 0)),
                    "last_seen": format_datetime(item.get("last_seen") or item.get("updated_at")),
                    "detail": item.get("detail") or item.get("message") or "Activité LLM",
                }
            )
        return rows

    rows = []
    generated_at = format_datetime(overview.get("generated_at"))
    items = providers if isinstance(providers, list) else providers.get("items", [])
    for item in items:
        rows.append(
            {
                "provider": item.get("name", "provider"),
                "model": item.get("model") or "—",
                "status": format_status_label(item.get("status")),
                "requests": item.get("requests", 0),
                "last_seen": generated_at,
                "detail": item.get("detail") or item.get("message") or "Statut agrégé depuis l'API",
            }
        )
    return rows


def build_llm_recent_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("recent_messages", []):
        rows.append(
            {
                "session": item.get("session_id") or item.get("session") or "—",
                "provider": item.get("provider") or "—",
                "model": item.get("model") or "—",
                "role": item.get("role") or "message",
                "created_at": format_datetime(item.get("created_at")),
                "content_preview": str(item.get("content_preview") or item.get("content") or "")[:160],
            }
        )
    return rows


def build_llm_sessions_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("sessions", []):
        rows.append(
            {
                "session_id": item.get("session_id") or item.get("id") or "—",
                "provider": item.get("provider") or "—",
                "model": item.get("model") or "—",
                "messages": item.get("message_count", item.get("messages", 0)),
                "started_at": format_datetime(item.get("started_at") or item.get("created_at")),
                "last_activity": format_datetime(item.get("last_activity") or item.get("updated_at")),
            }
        )
    return rows


def build_mcp_summary_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("summary", []):
        rows.append(
            {
                "component": item.get("component") or item.get("name") or "MCP",
                "status": format_status_label(item.get("status")),
                "detail": item.get("detail") or item.get("message") or "—",
                "updated_at": format_datetime(item.get("updated_at") or item.get("last_seen")),
            }
        )
    return rows


def build_mcp_servers_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("servers", []):
        rows.append(
            {
                "server": item.get("name") or item.get("server") or "server",
                "status": format_status_label(item.get("status")),
                "transport": item.get("transport") or "—",
                "endpoint": item.get("endpoint") or item.get("url") or "—",
                "tools": item.get("tool_count", item.get("tools", 0)),
            }
        )
    return rows


def build_mcp_tools_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("tools", []):
        rows.append(
            {
                "tool": item.get("name") or item.get("tool") or "tool",
                "server": item.get("server") or item.get("server_name") or "—",
                "status": format_status_label(item.get("status")),
                "calls": item.get("call_count", item.get("calls", 0)),
                "detail": item.get("detail") or item.get("description") or "—",
            }
        )
    return rows


def build_db_graph_diagram(payload: dict[str, Any]) -> str:
    explicit_diagram = str(payload.get("diagram") or "").strip()
    if explicit_diagram:
        return explicit_diagram

    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    if not nodes and not edges:
        return "Aucune donnée de graphe BDD disponible."

    lines = ["Schéma relationnel"]
    for node in nodes:
        node_name = node.get("id") or node.get("name") or "table"
        fields = node.get("fields") or []
        lines.append(f"[{node_name}]")
        for field in fields[:8]:
            field_name = field.get("name") if isinstance(field, dict) else str(field)
            lines.append(f"  - {field_name}")

    if edges:
        lines.append("")
        lines.append("Relations")
        for edge in edges:
            source = edge.get("source") or edge.get("from") or "?"
            target = edge.get("target") or edge.get("to") or "?"
            relation = edge.get("label") or edge.get("relation") or "references"
            lines.append(f"{source} -> {target} ({relation})")
    return "\n".join(lines)


def build_db_graph_nodes_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for node in payload.get("nodes", []):
        fields = node.get("fields") or []
        rows.append(
            {
                "table": node.get("id") or node.get("name") or "table",
                "fields": len(fields),
                "primary_key": node.get("primary_key") or node.get("pk") or "—",
                "detail": node.get("detail") or node.get("description") or "—",
            }
        )
    return rows


def build_db_graph_edges_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for edge in payload.get("edges", []):
        rows.append(
            {
                "source": edge.get("source") or edge.get("from") or "—",
                "target": edge.get("target") or edge.get("to") or "—",
                "relation": edge.get("label") or edge.get("relation") or "references",
                "field": edge.get("field") or edge.get("foreign_key") or "—",
            }
        )
    return rows