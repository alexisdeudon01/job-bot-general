from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from dashboard.pages.diagrams import render_page as render_diagrams_page
from dashboard.pages.entities import render_page as render_entities_page
from dashboard.pages.github_actions import render_page as render_github_actions_page
from dashboard.pages.live_logs import render_page as render_live_logs_page
from dashboard.pages.llm_history import render_page as render_llm_history_page
from dashboard.pages.overview import render_page as render_overview_page
from dashboard.pages.runs import render_page as render_runs_page
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import (
    build_db_graph_diagram,
    build_db_graph_edges_table,
    build_db_graph_nodes_table,
    build_mcp_servers_table,
    build_mcp_summary_rows,
    build_mcp_tools_table,
)

st.set_page_config(page_title="Job Bot Dashboard", layout="wide")


CUSTOM_CSS = """
<style>
.block-container {
    padding-top: 1.25rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
}
[data-testid="stSidebar"] * {
    color: #e5eefb;
}
.dashboard-shell {
    background: linear-gradient(135deg, #081120 0%, #0f172a 45%, #111827 100%);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 24px;
    padding: 1.25rem 1.25rem 0.25rem 1.25rem;
    box-shadow: 0 20px 60px rgba(15, 23, 42, 0.35);
    margin-bottom: 1rem;
}
.dashboard-hero {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    padding: 0.25rem 0 1rem 0;
}
.dashboard-hero h1 {
    margin: 0;
    color: #f8fafc;
    font-size: 2rem;
}
.dashboard-hero p {
    margin: 0.35rem 0 0 0;
    color: #cbd5e1;
}
.dashboard-chip-row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}
.dashboard-chip {
    background: rgba(59, 130, 246, 0.16);
    color: #dbeafe;
    border: 1px solid rgba(96, 165, 250, 0.28);
    border-radius: 999px;
    padding: 0.45rem 0.8rem;
    font-size: 0.9rem;
}
.dashboard-panel {
    background: rgba(15, 23, 42, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 18px;
    padding: 1rem;
    margin-bottom: 1rem;
}
.dashboard-panel h3,
.dashboard-panel h4,
.dashboard-panel label,
.dashboard-panel p,
.dashboard-panel span {
    color: #e2e8f0;
}
</style>
"""


def _apply_theme() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _render_shell_header() -> None:
    st.markdown(
        """
        <div class="dashboard-shell">
          <div class="dashboard-hero">
            <div>
              <h1>Job Bot Dashboard</h1>
              <p>Vue humaine, lisible et centralisée du pipeline, du MCP, de la base de données et des logs en direct.</p>
            </div>
            <div class="dashboard-chip-row">
              <div class="dashboard-chip">MCP ScrapeGraph</div>
              <div class="dashboard-chip">Monitoring pipeline</div>
              <div class="dashboard-chip">Architecture & BDD</div>
              <div class="dashboard-chip">Logs temps réel</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def init_session_state() -> None:
    if "dashboard_last_refresh_at" not in st.session_state:
        st.session_state.dashboard_last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "pipeline_last_result" not in st.session_state:
        st.session_state.pipeline_last_result = None
    if "job_url_input" not in st.session_state:
        st.session_state.job_url_input = ""
    if "cv_pdf_input" not in st.session_state:
        st.session_state.cv_pdf_input = ""
    if "dashboard_active_page" not in st.session_state:
        st.session_state.dashboard_active_page = "app"


def _extract_steps(result: dict[str, Any]) -> list[dict[str, Any]]:
    return result.get("steps", []) if isinstance(result, dict) else []


def _render_step(step: dict[str, Any], idx: int) -> None:
    name = step.get("step", f"step_{idx}")
    status = step.get("status", "unknown")
    detail = step.get("detail", "")
    output = step.get("output", {})

    icon = "✅" if status == "completed" else ("❌" if status == "failed" else "⏳")
    st.markdown(f"### {icon} {idx}. {name}")
    if detail:
        st.caption(detail)
    with st.expander("Output", expanded=False):
        st.json(output)


def _render_app_page(client: ApiClient) -> None:
    st.title("Pipeline candidature")
    st.caption("Entrer seulement l'URL du post et le CV PDF, puis lancer le pipeline MCP.")

    with st.container(border=True):
        st.subheader("Entrées")
        st.session_state.job_url_input = st.text_input(
            "URL du post",
            value=st.session_state.job_url_input,
            placeholder="https://company.com/jobs/123",
        )
        st.session_state.cv_pdf_input = st.text_input(
            "CV document path (PDF)",
            value=st.session_state.cv_pdf_input,
            placeholder="/path/to/your/cv.pdf  (optional)",
        )

        run_clicked = st.button("Run 12-step pipeline", type="primary", use_container_width=True)

    if run_clicked:
        payload = {
            "source": "dashboard",
            "payload": {
                "job_url": str(st.session_state.job_url_input or "").strip(),
                "cv_pdf_path": str(st.session_state.cv_pdf_input or "").strip(),
            },
            "options": {"mode": "mcp_first"},
        }
        result = client.post_json("/api/v1/pipeline/full", payload=payload, fallback={"status": "failed", "steps": []})
        st.session_state.pipeline_last_result = result
        st.session_state.dashboard_last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.divider()
    st.subheader("Actions / étapes du pipeline")

    result = st.session_state.pipeline_last_result
    if not result:
        st.info("Aucune exécution pour le moment.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Run ID", str(result.get("run_id", "—")))
        col2.metric("Type", str(result.get("pipeline_type", "full")))
        col3.metric("Status", str(result.get("status", "unknown")))

        steps = _extract_steps(result)
        if not steps:
            st.warning("Aucune étape retournée.")
        else:
            for i, step in enumerate(steps, start=1):
                _render_step(step, i)

        with st.expander("Réponse brute", expanded=False):
            st.json(result)


def _render_schema_architecture_page(client: ApiClient) -> None:
    st.title("Architecture BDD")
    st.caption("Vue détaillée du schéma relationnel exposé par l'API dashboard, avec fallback si l'endpoint n'est pas encore disponible.")

    db_graph = client.fetch_dashboard_db_graph()

    left_col, right_col = st.columns([1.1, 1])

    with left_col:
        st.subheader("Diagramme texte")
        st.code(build_db_graph_diagram(db_graph), language="text")

    with right_col:
        st.subheader("Relations")
        edge_rows = build_db_graph_edges_table(db_graph)
        if edge_rows:
            st.dataframe(edge_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune relation BDD détaillée disponible.")

    st.subheader("Tables")
    node_rows = build_db_graph_nodes_table(db_graph)
    if node_rows:
        st.dataframe(node_rows, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune table détaillée exposée par l'API.")

    with st.expander("Payload brut graphe BDD", expanded=False):
        st.json(db_graph)


def _render_mcp_page(client: ApiClient) -> None:
    st.title("MCP / Providers")
    st.caption("Vue détaillée des providers, serveurs MCP et outils exposés par l'API.")

    health = client.fetch_health()
    providers = client.fetch_provider_status()
    mcp_payload = client.fetch_dashboard_mcp()

    top_left, top_right = st.columns([1, 1])

    with top_left:
        st.subheader("Santé API")
        st.json(health, expanded=False)

    with top_right:
        st.subheader("Providers")
        if providers:
            st.dataframe(providers, use_container_width=True, hide_index=True)
        else:
            st.warning("Aucun statut provider disponible depuis l'API.")

    middle_left, middle_right = st.columns([1, 1])

    with middle_left:
        st.subheader("Résumé MCP")
        summary_rows = build_mcp_summary_rows(mcp_payload)
        if summary_rows:
            st.dataframe(summary_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun résumé MCP détaillé disponible.")

        st.subheader("Serveurs MCP")
        server_rows = build_mcp_servers_table(mcp_payload)
        if server_rows:
            st.dataframe(server_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun serveur MCP détaillé disponible.")

    with middle_right:
        st.subheader("Outils MCP")
        tool_rows = build_mcp_tools_table(mcp_payload)
        if tool_rows:
            st.dataframe(tool_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun outil MCP détaillé disponible.")

        st.subheader("Chaîne cible")
        st.code(
            """Dashboard Streamlit
  └── FastAPI orchestrator
        ├── providers status
        ├── pipeline runs
        ├── github actions
        ├── MCP servers
        └── MCP tools / calls""",
            language="text",
        )

    with st.expander("Payload brut MCP", expanded=False):
        st.json(mcp_payload)


def main() -> None:
    init_session_state()
    _apply_theme()
    client = ApiClient()

    _render_shell_header()
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Onglets",
        options=[
            ("app", "Pilotage"),
            ("overview", "Vue d'ensemble"),
            ("entities", "Entités"),
            ("runs", "Exécutions"),
            ("llm_history", "Historique IA"),
            ("github_actions", "GitHub Actions"),
            ("schema", "Schéma BDD"),
            ("diagrams", "Diagrammes"),
            ("mcp", "MCP & ScrapeGraph"),
            ("live_logs", "Logs en direct"),
        ],
        format_func=lambda item: item[1],
        index=0,
    )[0]

    st.session_state.dashboard_active_page = page

    if page == "app":
        _render_app_page(client)
    elif page == "overview":
        render_overview_page(client)
    elif page == "entities":
        render_entities_page(client)
    elif page == "runs":
        render_runs_page(client)
    elif page == "llm_history":
        render_llm_history_page(client)
    elif page == "github_actions":
        render_github_actions_page(client)
    elif page == "schema":
        _render_schema_architecture_page(client)
    elif page == "diagrams":
        render_diagrams_page()
    elif page == "mcp":
        _render_mcp_page(client)
    elif page == "live_logs":
        render_live_logs_page()

    st.divider()
    st.caption(f"Dernier refresh UI : {st.session_state.dashboard_last_refresh_at}")


if __name__ == "__main__":
    main()
