from __future__ import annotations

from datetime import datetime

import streamlit as st

from dashboard.components.sections import render_section_header
from dashboard.pages import (
    render_entities_page,
    render_github_actions_page,
    render_llm_history_page,
    render_overview_page,
    render_runs_page,
)
from dashboard.services.api_client import ApiClient

st.set_page_config(page_title="Job Bot Dashboard", layout="wide")


def init_session_state() -> None:
    if "dashboard_last_refresh_at" not in st.session_state:
        st.session_state.dashboard_last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "dashboard_auto_refresh" not in st.session_state:
        st.session_state.dashboard_auto_refresh = False
    if "dashboard_refresh_interval" not in st.session_state:
        st.session_state.dashboard_refresh_interval = 10


def render_sidebar() -> tuple[str, ApiClient]:
    st.sidebar.title("Job Bot Control Tower")
    st.sidebar.caption("Dashboard modulaire orienté API, observabilité, historique IA et orchestration.")

    api_base_url = st.sidebar.text_input(
        "Base URL API",
        value=ApiClient().base_url,
        help="URL de l'orchestrateur FastAPI. Exemple: http://localhost:8000",
    )

    client = ApiClient(base_url=api_base_url)

    pages = {
        "Overview": "Vue d’ensemble",
        "Entities": "Entités / OSINT / conformité",
        "Runs": "Pipeline runs / flux live",
        "GitHub Actions": "GitHub Actions",
        "LLM History": "Historique IA",
    }

    selected_page = st.sidebar.radio(
        "Navigation",
        options=list(pages.keys()),
        format_func=lambda key: pages[key],
    )

    st.sidebar.divider()
    st.sidebar.write("**Connectivité**")
    health = client.fetch_health()
    status = health.get("status", "unknown")
    if status == "ok":
        st.sidebar.success("API orchestrateur disponible")
    elif status == "unreachable":
        st.sidebar.warning("API indisponible, mode fallback")
    else:
        st.sidebar.info(f"État API : {status}")

    auto_refresh = st.sidebar.toggle("Auto-refresh (UI)", value=st.session_state.dashboard_auto_refresh)
    st.session_state.dashboard_auto_refresh = auto_refresh
    st.session_state.dashboard_refresh_interval = st.sidebar.slider(
        "Intervalle refresh (sec)",
        min_value=5,
        max_value=60,
        value=int(st.session_state.dashboard_refresh_interval),
        step=5,
    )

    if st.sidebar.button("Rafraîchir maintenant", use_container_width=True):
        st.session_state.dashboard_last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.rerun()

    st.sidebar.caption(f"Dernier refresh UI : {st.session_state.dashboard_last_refresh_at}")

    return selected_page, client


def render_header() -> None:
    st.title("🚀 Job Bot General — Control Tower")
    st.caption(
        "Cockpit API-first pour le pipeline CV ↔ offre ↔ IA, les entités métier, les runs temps réel, "
        "les historiques LLM et les workflows GitHub Actions."
    )


def render_footer() -> None:
    st.divider()
    render_section_header(
        "Architecture cible",
        "Le dashboard ne pilote plus directement des scripts locaux : il devient un client visuel de l’orchestrateur FastAPI "
        "et des microservices analyzer / generator / MCP.",
    )
    st.code(
        """[Streamlit Dashboard]
      |
      +--> GET /health
      +--> GET /api/v1/dashboard/overview
      +--> GET /api/v1/providers/status
      +--> GET /api/v1/pipeline/runs
      +--> POST /api/v1/pipeline/analyze
      +--> POST /api/v1/pipeline/generate
      +--> POST /api/v1/pipeline/full
      `--> GET /api/v1/github-actions/runs

[FastAPI Orchestrator]
      |
      +--> PostgreSQL
      +--> Redis
      +--> analyzer service
      +--> generator service
      `--> mcp adapter""",
        language="text",
    )
    st.info("Dashboard prêt — interface modulaire orientée observabilité, données et orchestration.")


def main() -> None:
    init_session_state()
    selected_page, client = render_sidebar()

    render_header()

    if selected_page == "Overview":
        render_overview_page(client)
    elif selected_page == "Entities":
        render_entities_page(client)
    elif selected_page == "Runs":
        render_runs_page(client)
    elif selected_page == "GitHub Actions":
        render_github_actions_page(client)
    elif selected_page == "LLM History":
        render_llm_history_page(client)

    render_footer()

    if st.session_state.dashboard_auto_refresh:
        st.caption(
            f"Auto-refresh activé ({st.session_state.dashboard_refresh_interval}s). "
            "Utiliser le rerun intégré du navigateur/Streamlit si nécessaire pendant la phase transitoire."
        )


if __name__ == "__main__":
    main()
