from __future__ import annotations

import streamlit as st

from dashboard.components.sections import render_json_section, render_section_header, render_table_section, render_text_diagram
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import build_runs_table, build_status_distribution


def _render_plotly_status_chart(distribution: list[dict[str, int]]) -> None:
    if not distribution:
        st.info("Aucune distribution de statuts à afficher.")
        return

    try:
        import plotly.express as px
    except ImportError:
        st.caption("Plotly non disponible pour le moment. Affichage tabulaire conservé.")
        st.dataframe(distribution, use_container_width=True, hide_index=True)
        return

    figure = px.bar(distribution, x="status", y="count", title="Distribution des statuts de runs")
    st.plotly_chart(figure, use_container_width=True)


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    runs_payload = client.fetch_pipeline_runs()
    run_rows = build_runs_table(runs_payload)
    distribution = build_status_distribution(runs_payload.get("items", []))

    render_section_header(
        "Runs pipeline",
        "Suivi des exécutions orchestrées par l'API. Cette page est compatible fallback et prête pour du quasi temps réel.",
    )

    top_col, bottom_col = st.columns([1.2, 1])

    with top_col:
        render_table_section("Liste des runs", run_rows, caption="Source : GET /api/v1/pipeline/runs")

    with bottom_col:
        _render_plotly_status_chart(distribution)
        render_text_diagram(
            "Séquence d'exécution",
            """POST /api/v1/pipeline/analyze
POST /api/v1/pipeline/generate
POST /api/v1/pipeline/full
            |
            v
GET /api/v1/pipeline/runs
            |
            v
Dashboard Streamlit""",
        )

    render_json_section("Payload brut runs", runs_payload)