from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from dashboard.services.api_client import ApiClient

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


def main() -> None:
    init_session_state()

    st.title("Pipeline candidature (simple)")
    st.caption("Entrer seulement l'URL du post et le CV PDF, puis lancer le pipeline MCP.")

    client = ApiClient()

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
                "job_url": st.session_state.job_url_input.strip(),
                "cv_pdf_path": st.session_state.cv_pdf_input.strip(),
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

    st.caption(f"Dernier refresh UI : {st.session_state.dashboard_last_refresh_at}")


if __name__ == "__main__":
    main()
