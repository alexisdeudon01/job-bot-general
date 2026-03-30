from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.utils.formatters import status_to_delta


def render_metric_row(metrics: list[dict[str, Any]]) -> None:
    if not metrics:
        st.info("Aucune métrique disponible.")
        return

    columns = st.columns(len(metrics))
    for column, metric in zip(columns, metrics):
        delta = metric.get("delta") or None
        delta_color = status_to_delta(metric.get("status") or delta)
        column.metric(metric.get("label", "Metric"), metric.get("value", "—"), delta=delta, delta_color=delta_color)


def render_status_badges(items: list[dict[str, Any]], title: str = "Statuts") -> None:
    with st.container(border=True):
        st.subheader(title)
        if not items:
            st.caption("Aucun statut disponible.")
            return

        for item in items:
            label = item.get("label") or item.get("name") or "élément"
            value = item.get("value") or item.get("status") or "unknown"
            st.markdown(f"- **{label}** : `{value}`")