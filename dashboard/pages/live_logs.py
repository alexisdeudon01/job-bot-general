from __future__ import annotations

import streamlit as st

from dashboard.components.sections import render_section_header, render_text_diagram
from dashboard.services.api_client import ApiClient


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    overview = client.fetch_dashboard_overview()
    runs_payload = client.fetch_pipeline_runs()
    recent_runs = overview.get("recent_runs") or overview.get("recent_pipeline_runs") or []
    run_items = runs_payload.get("runs") or runs_payload.get("items") or []

    render_section_header(
        "Logs en direct",
        "Lecture simple des derniers événements pipeline connus par l'API, en attendant un vrai flux temps réel.",
    )

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        st.subheader("Derniers événements observables")
        if recent_runs:
            st.dataframe(recent_runs, use_container_width=True, hide_index=True)
        elif run_items:
            st.dataframe(run_items[:20], use_container_width=True, hide_index=True)
        else:
            st.info("Aucun événement récent disponible pour le moment.")

    with col_right:
        render_text_diagram(
            "Principe du flux live",
            """Services Python
   |
   +--> pipeline runs
   +--> service runs
   +--> événements stockés
   |
   `--> Dashboard Streamlit
         rafraîchissement périodique""",
        )
        st.info(
            "Cette page propose un mode quasi temps réel basé sur les dernières exécutions connues."
        )

    st.caption("Étape suivante recommandée : ajouter un endpoint backend dédié aux événements structurés.")
    with st.expander("Payload brut utilisé", expanded=False):
        st.json(
            {
                "overview_recent_runs": recent_runs,
                "pipeline_runs": run_items[:20],
            }
        )
