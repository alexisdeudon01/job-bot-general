import streamlit as st
import json
from pathlib import Path

st.title("🚀 Job Bot General")

job_url = st.text_input("URL de l'offre")
cv_file = st.file_uploader("CV Europass", type=["txt", "pdf"])

if cv_file and st.button("Sauvegarder CV"):
    # code simplifié pour sauvegarder
    st.success("CV sauvegardé")

if st.button("Analyser"):
    st.info("Analyse lancée")
if st.button("Générer Europass"):
    st.info("Génération lancée")

st.info("Dashboard prêt - Accès : http://localhost:8501")
