from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

<<<<<<< HEAD
=======
<<<<<<< Updated upstream
from dashboard.services.api_client import ApiClient
=======
>>>>>>> 95144aa (kj)
from pages.entities import render_page as render_entities_page
from pages.github_actions import render_page as render_github_actions_page
from pages.llm_history import render_page as render_llm_history_page
from pages.overview import render_page as render_overview_page
from pages.runs import render_page as render_runs_page
from services.api_client import ApiClient
<<<<<<< HEAD
=======
from services.view_models import build_db_graph_diagram, build_db_graph_edges_table, build_db_graph_nodes_table, build_mcp_servers_table, build_mcp_summary_rows, build_mcp_tools_table
>>>>>>> Stashed changes
>>>>>>> 95144aa (kj)

st.set_page_config(page_title="Job Bot Dashboard", layout="wide")


def init_session_state() -> None:
    if "dashboard_last_refresh_at" not in st.session_state:
        st.session_state.dashboard_last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "pipeline_last_result" not in st.session_state:
        st.session_state.pipeline_last_result = None
    if "job_url_input" not in st.session_state:
        st.session_state.job_url_input = ""
    if "cv_pdf_input" not in st.session_state:
        st.session_state.cv_pdf_input = "data/cv.pdf"
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
            "Chemin CV PDF",
            value=st.session_state.cv_pdf_input,
            placeholder="data/cv.pdf",
        )

        run_clicked = st.button("Lancer pipeline 12 étapes", type="primary", use_container_width=True)

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

<<<<<<< HEAD

def _render_schema_architecture_page() -> None:
    st.title("Architecture BDD")
    st.caption("Vue synthétique du modèle de données actuellement connu par le projet.")

    st.markdown("### Entités principales")
    st.code(
        """organizations
  └── job_posts
        └── applications
              └── pipeline_runs
                    └── service_runs

providers
  └── llm_models
        └── chat_sessions
              └── chat_messages

github_workflows
  └── github_runs""",
        language="text",
    )

    st.info(
        "Cette vue est actuellement dérivée de la documentation et des pages dashboard existantes. "
        "Aucun endpoint backend dédié au graphe BDD n'est encore exposé."
    )

    st.markdown("### Ce qu'il manque pour une vraie vue graphique")
    st.markdown(
        "- un endpoint backend exposant le schéma\n"
        "- ou une génération Mermaid / Graphviz / ERD à partir des modèles SQLAlchemy\n"
        "- ou un fichier de diagramme versionné dans `docs/`"
    )
=======
<<<<<<< Updated upstream
=======

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
>>>>>>> 95144aa (kj)


def _render_mcp_page(client: ApiClient) -> None:
    st.title("MCP / Providers")
<<<<<<< HEAD
    st.caption("Visibilité opérationnelle minimale sur les providers et l'orchestration MCP.")

    health = client.fetch_health()
    providers = client.fetch_provider_status()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Santé API")
        st.json(health, expanded=False)

    with col2:
=======
    st.caption("Vue détaillée des providers, serveurs MCP et outils exposés par l'API.")

    health = client.fetch_health()
    providers = client.fetch_provider_status()
    mcp_payload = client.fetch_dashboard_mcp()

    top_left, top_right = st.columns([1, 1])

    with top_left:
        st.subheader("Santé API")
        st.json(health, expanded=False)

    with top_right:
>>>>>>> 95144aa (kj)
        st.subheader("Providers")
        if providers:
            st.dataframe(providers, use_container_width=True, hide_index=True)
        else:
            st.warning("Aucun statut provider disponible depuis l'API.")

<<<<<<< HEAD
    st.markdown("### Chaîne cible")
    st.code(
        """Dashboard Streamlit
=======
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
>>>>>>> 95144aa (kj)
  └── FastAPI orchestrator
        ├── providers status
        ├── pipeline runs
        ├── github actions
<<<<<<< HEAD
        └── MCP server / tools (à exposer davantage)""",
        language="text",
    )
=======
        ├── MCP servers
        └── MCP tools / calls""",
            language="text",
        )

    with st.expander("Payload brut MCP", expanded=False):
        st.json(mcp_payload)
>>>>>>> 95144aa (kj)


def main() -> None:
    init_session_state()
    client = ApiClient()

    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Onglets",
        options=[
            ("app", "App"),
            ("overview", "Overview"),
            ("entities", "Entités"),
            ("runs", "Runs"),
            ("llm_history", "Historique IA"),
            ("github_actions", "GitHub Actions"),
            ("schema", "Architecture BDD"),
            ("mcp", "MCP"),
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
<<<<<<< HEAD
        _render_schema_architecture_page()
=======
        _render_schema_architecture_page(client)
>>>>>>> 95144aa (kj)
    elif page == "mcp":
        _render_mcp_page(client)

    st.divider()
<<<<<<< HEAD
=======
>>>>>>> Stashed changes
>>>>>>> 95144aa (kj)
    st.caption(f"Dernier refresh UI : {st.session_state.dashboard_last_refresh_at}")


if __name__ == "__main__":
    main()