from __future__ import annotations

from typing import Any

from dashboard.utils.formatters import format_datetime, format_number, format_status_label


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _item_to_dict(item: Any, label: str = "value") -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if isinstance(item, str):
        text = item.strip()
        return {
            "name": text,
            "label": text,
            "value": text,
            "detail": text,
            "description": text,
            "status": text,
            label: text,
        }
    if item is None:
        return {}
    return {
        "name": str(item),
        "label": str(item),
        "value": item,
        "detail": str(item),
        "description": str(item),
        label: item,
    }


def build_overview_metrics(overview: dict[str, Any]) -> list[dict[str, str]]:
    overview = _safe_dict(overview)
    metrics = [_item_to_dict(metric, "value") for metric in _safe_list(overview.get("metrics", []))]
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
    runs = [_item_to_dict(run, "id") for run in _safe_list(runs)]
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
    for item in _safe_list(items):
        normalized = _item_to_dict(item, "status")
        status = format_status_label(normalized.get("status"))
        if not status:
            status = "unknown"
        counts[status] = counts.get(status, 0) + 1
    return [{"status": key, "count": value} for key, value in counts.items()]
def build_provider_cards(data: Any) -> list[dict[str, str]]:
    container = _safe_dict(data)
    items = data if isinstance(data, list) else container.get("items", [])
    cards = []
    for item in _safe_list(items):
        normalized = _item_to_dict(item, "detail")
        cards.append(
            {
                "name": str(normalized.get("name", "provider")),
                "status": format_status_label(normalized.get("status")),
                "detail": str(normalized.get("detail") or normalized.get("message") or "Aucun détail"),
            }
        )
    return cards


def build_runs_table(data: dict[str, Any]) -> list[dict[str, Any]]:
    data = _safe_dict(data)
    items = _safe_list(data.get("runs", data.get("items", [])))
    rows = []
    for item in items:
        normalized = _item_to_dict(item, "id")
        rows.append(
            {
                "id": normalized.get("id") or normalized.get("run_id"),
                "service": normalized.get("service_name") or normalized.get("service") or "pipeline",
                "status": format_status_label(normalized.get("status")),
                "started_at": format_datetime(normalized.get("started_at") or normalized.get("created_at")),
                "finished_at": format_datetime(normalized.get("finished_at") or normalized.get("updated_at")),
            }
        )
    return rows


def build_entities_table(overview: dict[str, Any]) -> list[dict[str, Any]]:
    overview = _safe_dict(overview)
    entity_payload = _safe_dict(overview.get("entities"))
    summary = [_item_to_dict(item, "count") for item in _safe_list(entity_payload.get("summary", []))]
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

    metrics = [_item_to_dict(metric, "value") for metric in _safe_list(overview.get("metrics", []))]
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
    payload = _safe_dict(payload)
    relationships = _safe_list(payload.get("relationships", []))
    rows = []
    for item in relationships:
        normalized = _item_to_dict(item, "relation")
        rows.append(
            {
                "source": normalized.get("source") or normalized.get("from") or "—",
                "target": normalized.get("target") or normalized.get("to") or "—",
                "relation": normalized.get("relation") or normalized.get("type") or "linked_to",
                "count": normalized.get("count", "—"),
            }
        )
    return rows


def build_entity_record_sections(payload: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    payload = _safe_dict(payload)
    records = _safe_dict(payload.get("records", {}))
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    for key, items in records.items():
        normalized_items = [_item_to_dict(item) for item in _safe_list(items)]
        if normalized_items:
            sections.append((str(key), normalized_items))
    return sections


def build_github_runs_table(data: Any) -> list[dict[str, Any]]:
    container = _safe_dict(data)
    items = data if isinstance(data, list) else container.get("items", [])
    rows = []
    for item in _safe_list(items):
        normalized = _item_to_dict(item, "workflow_name")
        rows.append(
            {
                "workflow": normalized.get("workflow_name") or normalized.get("name") or "workflow",
                "status": format_status_label(normalized.get("status") or normalized.get("conclusion")),
                "branch": normalized.get("branch") or normalized.get("head_branch") or "—",
                "started_at": format_datetime(normalized.get("started_at") or normalized.get("created_at")),
            }
        )
    return rows


def build_llm_history_rows(overview: dict[str, Any], providers: Any) -> list[dict[str, Any]]:
    overview = _safe_dict(overview)
    llm_payload = overview if overview.get("summary") is not None or overview.get("recent_messages") is not None else {}
    llm_payload = _safe_dict(llm_payload)
    summary = [_item_to_dict(item, "provider") for item in _safe_list(llm_payload.get("summary", []))]
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
    provider_container = _safe_dict(providers)
    items = providers if isinstance(providers, list) else provider_container.get("items", [])
    for item in _safe_list(items):
        normalized = _item_to_dict(item, "provider")
        rows.append(
            {
                "provider": normalized.get("name", "provider"),
                "model": normalized.get("model") or "—",
                "status": format_status_label(normalized.get("status")),
                "requests": normalized.get("requests", 0),
                "last_seen": generated_at,
                "detail": normalized.get("detail") or normalized.get("message") or "Statut agrégé depuis l'API",
            }
        )
    return rows


def build_llm_recent_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_dict(payload)
    rows = []
    for item in _safe_list(payload.get("recent_messages", [])):
        normalized = _item_to_dict(item, "content")
        rows.append(
            {
                "session": normalized.get("session_id") or normalized.get("session") or "—",
                "provider": normalized.get("provider") or "—",
                "model": normalized.get("model") or "—",
                "role": normalized.get("role") or "message",
                "created_at": format_datetime(normalized.get("created_at")),
                "content_preview": str(normalized.get("content_preview") or normalized.get("content") or "")[:160],
            }
        )
    return rows


def build_llm_sessions_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_dict(payload)
    rows = []
    for item in _safe_list(payload.get("sessions", [])):
        normalized = _item_to_dict(item, "session_id")
        rows.append(
            {
                "session_id": normalized.get("session_id") or normalized.get("id") or "—",
                "provider": normalized.get("provider") or "—",
                "model": normalized.get("model") or "—",
                "messages": normalized.get("message_count", normalized.get("messages", 0)),
                "started_at": format_datetime(normalized.get("started_at") or normalized.get("created_at")),
                "last_activity": format_datetime(normalized.get("last_activity") or normalized.get("updated_at")),
            }
        )
    return rows


def build_mcp_summary_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_dict(payload)
    rows = []
    for item in _safe_list(payload.get("summary", [])):
        normalized = _item_to_dict(item, "component")
        rows.append(
            {
                "component": normalized.get("component") or normalized.get("name") or "MCP",
                "status": format_status_label(normalized.get("status")),
                "detail": normalized.get("detail") or normalized.get("message") or "—",
                "updated_at": format_datetime(normalized.get("updated_at") or normalized.get("last_seen")),
            }
        )
    return rows


def build_mcp_servers_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_dict(payload)
    rows = []
    for item in _safe_list(payload.get("servers", [])):
        normalized = _item_to_dict(item, "server")
        rows.append(
            {
                "server": normalized.get("name") or normalized.get("server") or "server",
                "status": format_status_label(normalized.get("status")),
                "transport": normalized.get("transport") or "—",
                "endpoint": normalized.get("endpoint") or normalized.get("url") or "—",
                "tools": normalized.get("tool_count", normalized.get("tools", 0)),
            }
        )
    return rows


def build_mcp_tools_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_dict(payload)
    rows = []
    for item in _safe_list(payload.get("tools", [])):
        normalized = _item_to_dict(item, "tool")
        rows.append(
            {
                "tool": normalized.get("name") or normalized.get("tool") or "tool",
                "server": normalized.get("server") or normalized.get("server_name") or "—",
                "status": format_status_label(normalized.get("status")),
                "calls": normalized.get("call_count", normalized.get("calls", 0)),
                "detail": normalized.get("detail") or normalized.get("description") or "—",
            }
        )
    return rows


def build_db_graph_diagram(payload: dict[str, Any]) -> str:
    payload = _safe_dict(payload)
    explicit_diagram = str(payload.get("diagram") or "").strip()
    if explicit_diagram:
        return explicit_diagram

    nodes = _safe_list(payload.get("nodes", []))
    edges = _safe_list(payload.get("edges", []))
    if not nodes and not edges:
        return "Aucune donnée de graphe BDD disponible."

    lines = ["Schéma relationnel"]
    for node in nodes:
        normalized_node = _item_to_dict(node, "id")
        node_name = normalized_node.get("id") or normalized_node.get("name") or "table"
        fields = _safe_list(normalized_node.get("fields") or [])
        lines.append(f"[{node_name}]")
        for field in fields[:8]:
            field_dict = _item_to_dict(field, "name")
            field_name = field_dict.get("name") or str(field)
            lines.append(f"  - {field_name}")

    if edges:
        lines.append("")
        lines.append("Relations")
        for edge in edges:
            normalized_edge = _item_to_dict(edge, "source")
            source = normalized_edge.get("source") or normalized_edge.get("from") or "?"
            target = normalized_edge.get("target") or normalized_edge.get("to") or "?"
            relation = normalized_edge.get("label") or normalized_edge.get("relation") or "references"
            lines.append(f"{source} -> {target} ({relation})")
    return "\n".join(lines)


def build_db_graph_nodes_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_dict(payload)
    rows = []
    for node in _safe_list(payload.get("nodes", [])):
        normalized = _item_to_dict(node, "id")
        fields = _safe_list(normalized.get("fields") or [])
        rows.append(
            {
                "table": normalized.get("id") or normalized.get("name") or "table",
                "fields": len(fields),
                "primary_key": normalized.get("primary_key") or normalized.get("pk") or "—",
                "detail": normalized.get("detail") or normalized.get("description") or "—",
            }
        )
    return rows


def build_db_graph_edges_table(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_dict(payload)
    rows = []
    for edge in _safe_list(payload.get("edges", [])):
        normalized = _item_to_dict(edge, "source")
        rows.append(
            {
                "source": normalized.get("source") or normalized.get("from") or "—",
                "target": normalized.get("target") or normalized.get("to") or "—",
                "relation": normalized.get("label") or normalized.get("relation") or "references",
                "field": normalized.get("field") or normalized.get("foreign_key") or "—",
            }
        )
    return rows
