from __future__ import annotations

import streamlit as st

from dashboard.components.metrics import render_metric_row, render_status_badges
from dashboard.components.sections import render_json_section, render_section_header, render_table_section, render_text_diagram
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import (
    build_db_graph_diagram,
    build_db_graph_edges_table,
    build_db_graph_nodes_table,
    build_mcp_servers_table,
    build_mcp_summary_rows,
    build_mcp_tools_table,
    build_overview_metrics,
    build_pipeline_timeline_text,
    build_provider_cards,
)


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    overview = client.fetch_dashboard_overview()
    providers = client.fetch_provider_status()
    recent_runs = overview.get("recent_runs") or overview.get("recent_pipeline_runs") or []
    mcp_payload = client.fetch_dashboard_mcp()
    db_graph_payload = client.fetch_dashboard_db_graph()

    render_section_header(
        "Vue d'ensemble API-first",
        "Synthèse consolidée depuis l'orchestrateur FastAPI avec aperçus détaillés des runs, du MCP et du graphe BDD.",
    )
    render_metric_row(build_overview_metrics(overview))
    render_status_badges(build_provider_cards(providers), title="Fournisseurs IA")

    top_left, top_right = st.columns([1.2, 1])

    with top_left:
        render_table_section(
            "Runs récents",
            recent_runs,
            caption="Flux live prévu : cette section consomme /api/v1/dashboard/overview.",
        )

    with top_right:
        render_text_diagram(
            "Flux du dashboard",
            """Dashboard Streamlit
      |
      +--> GET /health
      +--> GET /api/v1/dashboard/overview
      +--> GET /api/v1/dashboard/entities
      +--> GET /api/v1/dashboard/llm-history
      +--> GET /api/v1/dashboard/mcp
      +--> GET /api/v1/dashboard/db-graph
      +--> GET /api/v1/providers/status
      +--> GET /api/v1/pipeline/runs
      `--> GET /api/v1/github-actions/runs""",
        )
        st.caption(build_pipeline_timeline_text(recent_runs))

    middle_left, middle_right = st.columns([1, 1])

    with middle_left:
        render_table_section(
            "Résumé MCP",
            build_mcp_summary_rows(mcp_payload),
            caption="Aperçu rapide de la santé des serveurs, outils et composants MCP.",
        )
        render_table_section("Serveurs MCP", build_mcp_servers_table(mcp_payload))

    with middle_right:
        render_text_diagram(
            "Graphe BDD",
            build_db_graph_diagram(db_graph_payload),
        )
        render_table_section("Relations BDD", build_db_graph_edges_table(db_graph_payload))

    render_table_section(
        "Tables BDD",
        build_db_graph_nodes_table(db_graph_payload),
        caption="Tables exposées par le backend pour la vue graphe de la base.",
    )
    render_table_section("Outils MCP", build_mcp_tools_table(mcp_payload))

    render_json_section("Payload brut overview", overview, caption="Utile pendant la phase de migration et d'intégration.")