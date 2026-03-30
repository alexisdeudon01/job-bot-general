from __future__ import annotations

import streamlit as st

from dashboard.components.sections import render_json_section, render_section_header, render_table_section, render_text_diagram
from dashboard.services.api_client import ApiClient
from dashboard.services.view_models import build_github_runs_table


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()
    github_payload = client.fetch_github_actions_runs()
    github_rows = build_github_runs_table(github_payload)

    render_section_header(
        "GitHub Actions",
        "Suivi des workflows CI/CD et automatisations connectées au projet. La page attend l'endpoint /api/v1/github-actions/runs.",
    )

    col1, col2 = st.columns([1.25, 1])

    with col1:
        render_table_section("Exécutions GitHub Actions", github_rows, caption="Compatible avec un backend progressif ou des stubs.")

    with col2:
        render_text_diagram(
            "Chaîne CI/CD",
            """GitHub
  |
  +--> workflow run
  +--> jobs
  +--> conclusion
  |
  v
FastAPI /api/v1/github-actions/runs
  |
  v
Dashboard Streamlit""",
        )

    render_json_section("Payload brut GitHub Actions", github_payload)