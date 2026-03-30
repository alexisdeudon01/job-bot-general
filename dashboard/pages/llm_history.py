from __future__ import annotations

import streamlit as st

from dashboard.components.sections import render_json_section, render_section_header, render_table_section, render_text_diagram
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import build_llm_history_rows


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    overview = client.fetch_dashboard_overview()
    providers = client.fetch_provider_status()
    rows = build_llm_history_rows(overview, providers)

    render_section_header(
        "Historique IA",
        "Prépare une vue consolidée des interactions providers / modèles / sessions. En attendant, la page s'appuie sur les statuts exposés par l'API.",
    )

    table_col, diagram_col = st.columns([1.2, 1])

    with table_col:
        render_table_section(
            "Activité providers",
            rows,
            caption="Base de travail pour relier plus tard providers, modèles LLM, chat_sessions et chat_messages.",
        )

    with diagram_col:
        render_text_diagram(
            "Projection cible",
            """providers
   |
   +--> llm_models
   |
   +--> chat_sessions
            |
            +--> chat_messages
            |
            `--> service_runs / pipeline_runs""",
        )

    render_json_section(
        "Payload brut providers",
        providers,
        caption="Utile pour brancher l'historique IA réel dès que les endpoints détaillés seront exposés.",
    )