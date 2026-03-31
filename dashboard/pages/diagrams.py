from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.components.sections import render_section_header

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _render_svg_asset(filename: str, caption: str) -> None:
    asset_path = ASSETS_DIR / filename
    if asset_path.exists():
        st.image(str(asset_path), use_container_width=True, caption=caption)
    else:
        st.warning(f"Fichier manquant : {filename}")


def render_page() -> None:
    render_section_header(
        "Diagrammes lisibles",
        "Vue simple et humaine de l'architecture applicative et de la base de données.",
    )

    tab_current, tab_target, tab_arch = st.tabs(
        [
            "ER actuel",
            "ER cible",
            "Architecture",
        ]
    )

    with tab_current:
        st.subheader("Schéma relationnel actuel")
        st.caption(
            "Vue des tables et relations actuellement implémentées dans l'application."
        )
        _render_svg_asset("er_current_schema.svg", "Diagramme ER actuel")
        st.info(
            "Cette vue aide à comprendre rapidement quelles tables existent déjà et comment elles se relient."
        )

    with tab_target:
        st.subheader("Schéma cible")
        st.caption("Projection métier plus complète pour la suite du produit.")
        _render_svg_asset("er_target_schema.svg", "Diagramme ER cible")
        st.info(
            "Cette vue distingue la cible fonctionnelle de l'état réellement implémenté aujourd'hui."
        )

    with tab_arch:
        st.subheader("Architecture du programme")
        st.caption("Chaîne complète entre dashboard, API, services, MCP et stockage.")
        _render_svg_asset("architecture_overview.svg", "Architecture générale")
        st.info(
            "Ce schéma donne une lecture directe du fonctionnement global du programme, sans jargon technique inutile."
        )
