from __future__ import annotations

import streamlit as st

from components.sections import render_json_section, render_section_header, render_table_section, render_text_diagram
from services.api_client import ApiClient
from services.view_models import build_llm_history_rows, build_llm_recent_messages, build_llm_sessions_table


def _build_llm_diagram() -> str:
    return """providers
   |
   +--> llm_models
   |        |
   |        `--> requests / responses
   |
   +--> chat_sessions
   |        |
   |        `--> chat_messages
   |
   `--> pipeline_runs / service_runs"""


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    llm_payload = client.fetch_dashboard_llm_history()
    overview = client.fetch_dashboard_overview()
    providers = client.fetch_provider_status()

    summary_rows = build_llm_history_rows(llm_payload, providers)
    recent_messages = build_llm_recent_messages(llm_payload)
    session_rows = build_llm_sessions_table(llm_payload)

    render_section_header(
        "Historique IA réel",
        "Vue consolidée des providers, modèles, sessions et messages récents. Fallback automatique sur les données overview/providers si nécessaire.",
    )

    top_left, top_right = st.columns([1.2, 1])

    with top_left:
        render_table_section(
            "Synthèse activité LLM",
            summary_rows,
            caption="Source privilégiée : GET /api/v1/dashboard/llm-history",
        )

    with top_right:
        render_text_diagram("Projection des relations LLM", _build_llm_diagram())

    middle_left, middle_right = st.columns([1.2, 1])

    with middle_left:
        render_table_section(
            "Messages récents",
            recent_messages,
            caption="Extraits récents des interactions LLM pour audit et debugging.",
        )

    with middle_right:
        render_table_section(
            "Sessions",
            session_rows,
            caption="Sessions agrégées par provider / modèle pour suivre l'activité réelle.",
        )

    if not recent_messages and not session_rows and summary_rows:
        st.info("L'API ne renvoie pas encore les détails des messages/sessions ; la synthèse providers reste affichée.")

    render_json_section(
        "Payload brut LLM history",
        llm_payload or overview.get("llm_history", {}),
        caption="Payload utile pour valider l'intégration backend de l'historique LLM.",
    )