from __future__ import annotations

import time
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

st.set_page_config(
    page_title="Job Bot — Lettre de motivation",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
.block-container { padding-top: 1.25rem; padding-bottom: 2rem; max-width: 1400px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #111827 100%); }
[data-testid="stSidebar"] * { color: #e5eefb; }
.cover-letter-box {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    border: 1px solid rgba(96,165,250,0.35);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin: 1rem 0;
    color: #f1f5f9;
    font-size: 1.05rem;
    line-height: 1.8;
    white-space: pre-wrap;
    font-family: 'Georgia', serif;
}
.step-completed { border-left: 4px solid #22c55e; padding-left: 0.75rem; margin: 0.5rem 0; }
.step-failed    { border-left: 4px solid #ef4444; padding-left: 0.75rem; margin: 0.5rem 0; }
.step-skipped   { border-left: 4px solid #94a3b8; padding-left: 0.75rem; margin: 0.5rem 0; }
.step-running   { border-left: 4px solid #f59e0b; padding-left: 0.75rem; margin: 0.5rem 0; }
.prompt-box {
    background: #0f172a;
    border: 1px solid rgba(148,163,184,0.2);
    border-radius: 8px;
    padding: 1rem;
    font-family: monospace;
    font-size: 0.85rem;
    color: #94a3b8;
    white-space: pre-wrap;
    max-height: 400px;
    overflow-y: auto;
}
.metric-chip {
    display: inline-block;
    background: rgba(59,130,246,0.15);
    color: #93c5fd;
    border: 1px solid rgba(96,165,250,0.3);
    border-radius: 999px;
    padding: 0.3rem 0.8rem;
    font-size: 0.85rem;
    margin: 0.2rem;
}
</style>
"""


def _apply_theme() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def init_session_state() -> None:
    defaults = {
        "pipeline_last_result": None,
        "job_url_input": "",
        "cv_pdf_input": "",
        "dashboard_last_refresh_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "active_page": "Pilotage",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─────────────────────────────────────────────────────────────────────────────
# Step rendering helpers
# ─────────────────────────────────────────────────────────────────────────────

STATUS_ICON = {
    "completed": "✅",
    "failed": "❌",
    "skipped": "⏭️",
    "partial": "⚠️",
    "running": "⏳",
    "unknown": "❓",
}

STATUS_CLASS = {
    "completed": "step-completed",
    "failed": "step-failed",
    "skipped": "step-skipped",
    "partial": "step-running",
    "running": "step-running",
    "unknown": "step-skipped",
}


def _render_step(step: dict[str, Any], idx: int) -> None:
    name = step.get("step", f"step_{idx}")
    status = step.get("status", "unknown")
    detail = step.get("detail", "")
    output = step.get("output", {})

    icon = STATUS_ICON.get(status, "❓")
    css_class = STATUS_CLASS.get(status, "step-skipped")

    st.markdown(
        f'<div class="{css_class}"><strong>{icon} {idx}. {name}</strong></div>',
        unsafe_allow_html=True,
    )
    if detail:
        st.caption(detail)

    # Show tool used inline
    tool = output.get("tool", "")
    if tool and tool != "none":
        st.markdown(
            f'<span class="metric-chip">🔧 {tool}</span>',
            unsafe_allow_html=True,
        )

    # Show prompt used (collapsible)
    prompt_used = output.get("prompt_used", "")
    if prompt_used:
        with st.expander("📝 Prompt envoyé à OpenAI", expanded=False):
            st.markdown(
                f'<div class="prompt-box">{prompt_used}</div>',
                unsafe_allow_html=True,
            )

    # Show cover letter prominently
    cover_letter = output.get("cover_letter", "")
    if cover_letter and not cover_letter.startswith("Erreur:"):
        st.markdown("#### 📄 Lettre de motivation générée")
        st.markdown(
            f'<div class="cover-letter-box">{cover_letter}</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label="⬇️ Télécharger la lettre (.txt)",
            data=cover_letter,
            file_name="lettre_de_motivation.txt",
            mime="text/plain",
            key=f"dl_cover_{idx}",
        )

    # Show fit assessment
    fit_assessment = output.get("fit_assessment", "")
    if fit_assessment:
        with st.expander("🎯 Analyse d'adéquation candidat/poste", expanded=True):
            st.markdown(fit_assessment)

    # Show other output details
    with st.expander("🔍 Détails de l'étape", expanded=False):
        # Filter out large text fields already shown above
        filtered = {
            k: v
            for k, v in output.items()
            if k
            not in (
                "cover_letter",
                "prompt_used",
                "fit_assessment",
                "content_preview",
                "cv_preview",
            )
            and not (isinstance(v, str) and len(v) > 500)
        }
        if filtered:
            st.json(filtered)
        # Show previews separately
        if output.get("content_preview"):
            st.caption("Aperçu contenu scraped:")
            st.text(output["content_preview"][:400])
        if output.get("cv_preview"):
            st.caption("Aperçu CV:")
            st.text(output["cv_preview"][:300])


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline page
# ─────────────────────────────────────────────────────────────────────────────


def _render_app_page(client: ApiClient) -> None:
    st.title("🚀 Générateur de lettre de motivation")
    st.caption(
        "Entrez l'URL du poste et optionnellement votre CV PDF. "
        "Le pipeline scrape l'offre, analyse votre profil et génère une lettre de motivation via OpenAI."
    )

    # ── Input form ────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("📋 Entrées")
        col_url, col_cv = st.columns([2, 1])

        with col_url:
            st.session_state.job_url_input = st.text_input(
                "🔗 URL de l'offre d'emploi",
                value=st.session_state.job_url_input,
                placeholder="https://company.com/jobs/software-engineer",
                help="URL complète de l'offre d'emploi à analyser",
            )

        with col_cv:
            st.session_state.cv_pdf_input = st.text_input(
                "📄 Chemin vers votre CV (PDF)",
                value=st.session_state.cv_pdf_input,
                placeholder="/path/to/cv.pdf  (optionnel)",
                help="Chemin absolu vers votre CV en PDF",
            )

        run_clicked = st.button(
            "▶️ Générer la lettre de motivation",
            type="primary",
            use_container_width=True,
        )

    # ── Pipeline execution with progress ─────────────────────────────────────
    if run_clicked:
        job_url = str(st.session_state.job_url_input or "").strip()
        cv_path = str(st.session_state.cv_pdf_input or "").strip()

        if not job_url:
            st.warning("⚠️ Veuillez entrer une URL d'offre d'emploi.")
            return

        payload = {
            "source": "dashboard",
            "payload": {
                "job_url": job_url,
                "cv_pdf_path": cv_path,
            },
            "options": {"mode": "mcp_first_openai_agents"},
        }

        # Show animated progress while waiting for the backend
        progress_placeholder = st.empty()
        with progress_placeholder.container():
            with st.status(
                "⚙️ Pipeline en cours d'exécution...", expanded=True
            ) as status_widget:
                st.write(
                    "🔍 Étape 1 — Scraping de l'offre d'emploi via ScrapeGraph MCP..."
                )
                time.sleep(0.3)
                st.write("📄 Étape 2 — Lecture du CV PDF...")
                time.sleep(0.2)
                st.write(
                    "🤖 Étape 3 — Génération de la lettre de motivation via OpenAI..."
                )
                st.write("🎯 Étape 4 — Analyse d'adéquation candidat/poste...")

                result = client.post_json(
                    "/api/v1/pipeline/full",
                    payload=payload,
                    fallback={
                        "status": "failed",
                        "steps": [],
                        "error": "API unreachable",
                    },
                )

                if result.get("status") in ("completed", "partial"):
                    status_widget.update(
                        label="✅ Pipeline terminé !", state="complete", expanded=False
                    )
                else:
                    status_widget.update(
                        label="❌ Pipeline échoué", state="error", expanded=False
                    )

        progress_placeholder.empty()

        st.session_state.pipeline_last_result = result
        st.session_state.dashboard_last_refresh_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        st.rerun()

    # ── Results display ───────────────────────────────────────────────────────
    st.divider()

    result = st.session_state.pipeline_last_result
    if not result:
        st.info(
            "💡 Entrez une URL d'offre d'emploi et cliquez sur **Générer la lettre de motivation**."
        )
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Run ID", str(result.get("run_id", "—"))[-8:])
    col2.metric("Type", str(result.get("pipeline_type", "full")))
    col3.metric("Statut", str(result.get("status", "unknown")))
    steps = result.get("steps", [])
    col4.metric(
        "Étapes",
        f"{sum(1 for s in steps if s.get('status') == 'completed')}/{len(steps)}",
    )

    # Quick cover letter extraction for top display
    cover_letter_top = ""
    for step in steps:
        output = step.get("output", {})
        cl = output.get("cover_letter", "")
        if cl and not cl.startswith("Erreur:"):
            cover_letter_top = cl
            break

    if cover_letter_top:
        st.success("✅ Lettre de motivation générée avec succès !")
        st.markdown("## 📄 Votre lettre de motivation")
        st.markdown(
            f'<div class="cover-letter-box">{cover_letter_top}</div>',
            unsafe_allow_html=True,
        )
        col_dl1, col_dl2 = st.columns([1, 3])
        with col_dl1:
            st.download_button(
                label="⬇️ Télécharger (.txt)",
                data=cover_letter_top,
                file_name="lettre_de_motivation.txt",
                mime="text/plain",
                key="dl_cover_top",
            )

    # Fit assessment quick display
    for step in steps:
        output = step.get("output", {})
        fit = output.get("fit_assessment", "")
        if fit:
            with st.expander("🎯 Analyse d'adéquation candidat/poste", expanded=False):
                st.markdown(fit)
            break

    # Detailed steps
    st.divider()
    st.subheader("🔬 Détail des étapes du pipeline")

    if not steps:
        st.warning("Aucune étape retournée par le pipeline.")
        if result.get("error"):
            st.error(f"Erreur: {result['error']}")
    else:
        for i, step in enumerate(steps, start=1):
            with st.expander(
                f"{STATUS_ICON.get(step.get('status', 'unknown'), '❓')} Étape {i}: {step.get('step', '')} — {step.get('detail', '')}",
                expanded=(step.get("status") == "failed"),
            ):
                _render_step(step, i)

    with st.expander("📦 Réponse brute JSON", expanded=False):
        st.json(result)


# ─────────────────────────────────────────────────────────────────────────────
# Other pages
# ─────────────────────────────────────────────────────────────────────────────


def _render_schema_architecture_page(client: ApiClient) -> None:
    st.title("Architecture BDD")
    st.caption("Vue détaillée du schéma relationnel exposé par l'API dashboard.")

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
        ├── MCP servers (ScrapeGraph stdio)
        └── OpenAI Agents SDK""",
            language="text",
        )

    with st.expander("Payload brut MCP", expanded=False):
        st.json(mcp_payload)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

PAGE_OPTIONS = [
    "Pilotage",
    "Vue d'ensemble",
    "Entités",
    "Exécutions",
    "Historique IA",
    "GitHub Actions",
    "Schéma BDD",
    "Diagrammes",
    "MCP & ScrapeGraph",
    "Logs en direct",
]


def main() -> None:
    init_session_state()
    _apply_theme()
    client = ApiClient()

    # ── Sidebar navigation ────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🤖 Job Bot")
        st.markdown("*Générateur de lettres de motivation*")
        st.divider()

        page = st.radio(
            "Navigation",
            options=PAGE_OPTIONS,
            index=PAGE_OPTIONS.index(st.session_state.active_page),
            label_visibility="collapsed",
        )
        st.session_state.active_page = page

        st.divider()
        st.caption(f"Refresh: {st.session_state.dashboard_last_refresh_at}")

    # ── Page routing ──────────────────────────────────────────────────────────
    if page == "Pilotage":
        _render_app_page(client)
    elif page == "Vue d'ensemble":
        render_overview_page(client)
    elif page == "Entités":
        render_entities_page(client)
    elif page == "Exécutions":
        render_runs_page(client)
    elif page == "Historique IA":
        render_llm_history_page(client)
    elif page == "GitHub Actions":
        render_github_actions_page(client)
    elif page == "Schéma BDD":
        _render_schema_architecture_page(client)
    elif page == "Diagrammes":
        render_diagrams_page()
    elif page == "MCP & ScrapeGraph":
        _render_mcp_page(client)
    elif page == "Logs en direct":
        render_live_logs_page()


if __name__ == "__main__":
    main()
