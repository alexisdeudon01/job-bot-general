from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.components.sections import render_json_section, render_section_header, render_table_section
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import build_entities_table


def _build_entity_notes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "entity": row.get("entity"),
            "usage": "Base de navigation dashboard / analytics / filtrage",
            "count": row.get("count", 0),
        }
        for row in rows
    ]


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    overview = client.fetch_dashboard_overview()
    entity_rows = build_entities_table(overview)

    render_section_header(
        "Entités métier",
        "Prépare la navigation future autour des organisations, offres, candidatures et relations métier exposées par l'API.",
    )

    table_col, notes_col = st.columns([1.1, 1])

    with table_col:
        render_table_section("Volumes agrégés", entity_rows, caption="Source actuelle : /api/v1/dashboard/overview > summary")

    with notes_col:
        render_table_section(
            "Préparation UX",
            _build_entity_notes(entity_rows),
            caption="Cette page servira ensuite de point d'entrée vers les écrans détaillés entités/relations.",
        )

    render_json_section("Payload brut entités", overview.get("summary", {}))