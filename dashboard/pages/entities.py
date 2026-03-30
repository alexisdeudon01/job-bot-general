from __future__ import annotations

import streamlit as st

from dashboard.components.sections import render_json_section, render_section_header, render_table_section, render_text_diagram
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import build_entities_table, build_entity_record_sections, build_entity_relationship_rows


def _build_entity_notes(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    notes = []
    for row in rows:
        notes.append(
            {
                "entity": row.get("entity"),
                "usage": "Navigation dashboard / analytics / filtres métier",
                "count": row.get("count", 0),
                "description": row.get("description") or "—",
            }
        )
    return notes


def _build_relationship_diagram(relationships: list[dict[str, object]]) -> str:
    if not relationships:
        return "Aucune relation détaillée disponible."

    lines = ["Relations métier"]
    for item in relationships[:16]:
        source = item.get("source") or "?"
        relation = item.get("relation") or "linked_to"
        target = item.get("target") or "?"
        lines.append(f"{source} --{relation}--> {target}")
    return "\n".join(lines)


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    entities_payload = client.fetch_dashboard_entities()
    overview = client.fetch_dashboard_overview()

    merged_payload = entities_payload if isinstance(entities_payload, dict) else {}
    if not merged_payload:
        merged_payload = overview.get("entities", {}) if isinstance(overview, dict) else {}

    entity_rows = build_entities_table({"entities": merged_payload, "metrics": overview.get("metrics", [])})
    relationship_rows = build_entity_relationship_rows(merged_payload)
    record_sections = build_entity_record_sections(merged_payload)

    render_section_header(
        "Entités métier détaillées",
        "Vue détaillée des volumes, relations et exemples d'enregistrements exposés par l'API dashboard.",
    )

    top_left, top_right = st.columns([1.15, 1])

    with top_left:
        render_table_section(
            "Volumes par entité",
            entity_rows,
            caption="Source privilégiée : GET /api/v1/dashboard/entities, avec fallback sur /api/v1/dashboard/overview",
        )

    with top_right:
        render_table_section(
            "Préparation UX / usages",
            _build_entity_notes(entity_rows),
            caption="Aide à la navigation future entre listes, détails et graphes relationnels.",
        )

    bottom_left, bottom_right = st.columns([1.1, 1])

    with bottom_left:
        render_table_section(
            "Relations métier",
            relationship_rows,
            caption="Permet de visualiser les dépendances entre organisations, offres, candidatures et runs.",
        )

    with bottom_right:
        render_text_diagram("Diagramme relationnel", _build_relationship_diagram(relationship_rows))

    if record_sections:
        st.markdown("### Exemples d'enregistrements")
        for section_name, rows in record_sections:
            render_table_section(
                f"{section_name}",
                rows[:25],
                caption="Extraits fournis par l'API pour inspection rapide côté dashboard.",
            )
    else:
        st.info("Aucun exemple d'enregistrement détaillé n'a été retourné par l'API.")

    render_json_section("Payload brut entités", merged_payload)