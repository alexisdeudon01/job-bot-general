from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from dashboard.components.sections import render_section_header, render_table_section
from dashboard.services.api_client import ApiClient


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_requirements(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _compute_data_quality(overview: dict[str, Any], runs_payload: dict[str, Any], db_graph: dict[str, Any]) -> dict[str, Any]:
    runs = _safe_list(runs_payload.get("runs"))
    statuses = [str(item.get("status", "unknown")).lower() for item in runs if isinstance(item, dict)]
    total_runs = len(statuses)
    failed = sum(1 for status in statuses if status in {"failed", "error"})
    completed = sum(1 for status in statuses if status == "completed")

    fallback_flags = [
        bool(_safe_dict(overview).get("fallback")),
        bool(_safe_dict(runs_payload).get("fallback")),
        bool(_safe_dict(db_graph).get("fallback")),
    ]
    fallback_count = sum(1 for flag in fallback_flags if flag)

    completeness_checks = [
        len(_safe_list(overview.get("metrics"))) > 0,
        len(_safe_list(overview.get("services"))) > 0,
        len(_safe_list(db_graph.get("nodes"))) > 0,
    ]
    completeness_score = round((sum(1 for check in completeness_checks if check) / len(completeness_checks)) * 100, 1)

    reliability_score = max(0.0, round(100 - (fallback_count * 20) - ((failed / total_runs) * 100 if total_runs else 0), 1))

    return {
        "total_runs": total_runs,
        "completed_runs": completed,
        "failed_runs": failed,
        "failure_rate_pct": round((failed / total_runs) * 100, 1) if total_runs else 0.0,
        "fallback_count": fallback_count,
        "completeness_score_pct": completeness_score,
        "reliability_score_pct": reliability_score,
    }


def _build_dependency_redundancies() -> list[dict[str, Any]]:
    root_requirements = _load_requirements(Path("requirements.txt"))
    dashboard_requirements = _load_requirements(Path("dashboard/requirements.txt"))

    root_norm = {package.lower(): package for package in root_requirements}
    dashboard_norm = {package.lower(): package for package in dashboard_requirements}

    duplicates = sorted(set(root_norm.keys()) & set(dashboard_norm.keys()))
    rows: list[dict[str, Any]] = []
    for package in duplicates:
        rows.append(
            {
                "type": "cross-file duplicate",
                "package": package,
                "location": "requirements.txt + dashboard/requirements.txt",
                "priority": "medium",
            }
        )

    suspicious_pairs = [
        ("pypdf", "pypdf2"),
        ("pypdf", "PyPDF2".lower()),
    ]
    for left, right in suspicious_pairs:
        if left in root_norm and right in root_norm:
            rows.append(
                {
                    "type": "possible functional overlap",
                    "package": f"{left} / {right}",
                    "location": "requirements.txt",
                    "priority": "high",
                }
            )

    return rows


def _build_bug_signals(overview: dict[str, Any], runs_payload: dict[str, Any], db_graph: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []

    if _safe_dict(overview).get("fallback"):
        signals.append(
            {
                "signal": "overview fallback actif",
                "impact": "Le dashboard montre des données de secours, pas les données live",
                "priority": "high",
            }
        )

    run_items = _safe_list(runs_payload.get("runs"))
    if run_items:
        failed_runs = [run for run in run_items if isinstance(run, dict) and str(run.get("status", "")).lower() in {"failed", "error"}]
        if failed_runs:
            signals.append(
                {
                    "signal": "runs en échec détectés",
                    "impact": f"{len(failed_runs)} run(s) échoués à investiguer",
                    "priority": "high",
                }
            )

    nodes = _safe_list(db_graph.get("nodes"))
    edges = _safe_list(db_graph.get("edges"))
    if nodes and not edges:
        signals.append(
            {
                "signal": "graphe DB sans relation",
                "impact": "Les FK semblent absentes ou non exposées",
                "priority": "medium",
            }
        )

    if not signals:
        signals.append(
            {
                "signal": "aucune anomalie bloquante détectée",
                "impact": "Sur la base des données API actuellement disponibles",
                "priority": "low",
            }
        )

    return signals


def render_page(api_client: ApiClient | None = None) -> None:
    client = api_client or ApiClient()

    overview = _safe_dict(client.fetch_dashboard_overview())
    runs_payload = _safe_dict(client.fetch_pipeline_runs())
    db_graph = _safe_dict(client.fetch_dashboard_db_graph())

    quality = _compute_data_quality(overview, runs_payload, db_graph)
    bug_signals = _build_bug_signals(overview, runs_payload, db_graph)
    redundancy_rows = _build_dependency_redundancies()

    render_section_header(
        "Diagnostic data-oriented",
        "Détection de bugs potentiels, redondances de dépendances et score de fiabilité basé sur les données API.",
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fiabilité", f"{quality['reliability_score_pct']}%")
    col2.metric("Complétude", f"{quality['completeness_score_pct']}%")
    col3.metric("Taux d'échec runs", f"{quality['failure_rate_pct']}%")
    col4.metric("Endpoints fallback", quality["fallback_count"])

    render_table_section("Signaux bugs", bug_signals, caption="Détection heuristique orientée exploitation.")

    if redundancy_rows:
        render_table_section(
            "Redondances détectées",
            redundancy_rows,
            caption="Analyse statique des fichiers requirements pour identifier les recouvrements.",
        )
    else:
        st.success("Aucune redondance évidente détectée dans les dépendances inspectées.")

    with st.expander("Données sources utilisées", expanded=False):
        st.json(
            {
                "overview": overview,
                "pipeline_runs": runs_payload,
                "db_graph": db_graph,
            },
            expanded=False,
        )
