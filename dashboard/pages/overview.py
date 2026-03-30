from __future__ import annotations

import streamlit as st

from dashboard.components.metrics import render_metric_row, render_status_badges
from dashboard.components.sections import render_json_section, render_section_header, render_table_section, render_text_diagram
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import build_overview_metrics, build_pipeline_timeline_text, build_provider_cards


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    overview = client.fetch_dashboard_overview()
    providers = client.fetch_provider_status()

    render_section_header(
        "Vue d'ensemble API-first",
        "Synthèse consolidée depuis l'orchestrateur FastAPI. Le dashboard reste robuste même si l'API n'est pas encore disponible.",
    )
    render_metric_row(build_overview_metrics(overview))
    render_status_badges(build_provider_cards(providers), title="Fournisseurs IA")

    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        render_table_section(
            "Runs récents",
            overview.get("recent_runs", []),
            caption="Flux live prévu : cette section est prête à consommer les runs exposés par /api/v1/dashboard/overview.",
        )

    with right_col:
        render_text_diagram(
            "Flux du dashboard",
            """Dashboard Streamlit
      |
      +--> GET /health
      +--> GET /api/v1/dashboard/overview
      +--> GET /api/v1/providers/status
      +--> GET /api/v1/pipeline/runs
      `--> GET /api/v1/github-actions/runs""",
        )
        st.caption(build_pipeline_timeline_text(overview.get("recent_runs", [])))

    render_json_section("Payload brut overview", overview, caption="Utile pendant la phase de migration et d'intégration.")