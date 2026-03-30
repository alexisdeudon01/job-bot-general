from __future__ import annotations

from typing import Any

import streamlit as st


def render_section_header(title: str, caption: str | None = None) -> None:
    st.subheader(title)
    if caption:
        st.caption(caption)


def render_key_value_block(title: str, data: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if not data:
            st.caption("Aucune donnée disponible.")
            return

        for key, value in data.items():
            st.write(f"**{key}** : {value}")


def render_text_diagram(title: str, diagram: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.code(diagram, language="text")


def render_table_section(title: str, rows: list[dict[str, Any]], caption: str | None = None) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if caption:
            st.caption(caption)

        if not rows:
            st.info("Aucune donnée disponible.")
            return

        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_json_section(title: str, payload: Any, caption: str | None = None) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if caption:
            st.caption(caption)
        st.json(payload, expanded=False)