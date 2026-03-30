import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st


st.set_page_config(page_title="Job Bot Dashboard", layout="wide")

DATA_DIR = Path("/data")
OUTPUT_DIR = Path("/output")
APP_DIR = Path("/app")
CV_PDF_PATH = DATA_DIR / "cv.pdf"
CV_TXT_PATH = DATA_DIR / "resume_europass.txt"
JOB_DATA_PATH = OUTPUT_DIR / "job_data.json"
GENERATION_RESULTS_PATH = OUTPUT_DIR / "generation_results.json"
ANALYZER_SCRIPT_PATH = APP_DIR / "analyzer" / "main.py"
GENERATOR_SCRIPT_PATH = APP_DIR / "generator" / "main.py"


def init_session_state():
    if "dashboard_logs" not in st.session_state:
        st.session_state.dashboard_logs = []
    if "last_run_at" not in st.session_state:
        st.session_state.last_run_at = None
    if "last_refresh_at" not in st.session_state:
        st.session_state.last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "job_url" not in st.session_state:
        st.session_state.job_url = ""
    if "last_action_status" not in st.session_state:
        st.session_state.last_action_status = {
            "analyse": "idle",
            "generation": "idle",
        }
    if "last_command_details" not in st.session_state:
        st.session_state.last_command_details = {
            "analyse": {"command": "", "returncode": None},
            "generation": {"command": "", "returncode": None},
        }


def add_log(message, level="INFO", source="dashboard"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{source.upper()}] [{level.upper()}] {message}"
    st.session_state.dashboard_logs.append(entry)
    st.session_state.dashboard_logs = st.session_state.dashboard_logs[-500:]


def ensure_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(uploaded_file, destination: Path):
    ensure_directory(destination.parent)
    destination.write_bytes(uploaded_file.getbuffer())


def read_json_file(path: Path):
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        add_log(f"Le fichier {path} contient un JSON invalide: {exc}", level="ERROR", source="lecture")
        return {"_error": f"JSON invalide: {exc}"}
    except Exception as exc:
        add_log(f"Impossible de lire {path}: {exc}", level="ERROR", source="lecture")
        return {"_error": str(exc)}


def get_file_info(path: Path):
    if not path.exists():
        return {
            "exists": False,
            "size": 0,
            "modified_at": None,
            "name": path.name,
        }

    stat = path.stat()
    return {
        "exists": True,
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "name": path.name,
    }


def summarize_data(data):
    if data is None:
        return {"type": "absent", "count": 0, "keys": []}
    if isinstance(data, dict):
        return {"type": "dict", "count": len(data), "keys": list(data.keys())[:20]}
    if isinstance(data, list):
        return {"type": "list", "count": len(data), "keys": []}
    return {"type": type(data).__name__, "count": 1, "keys": []}


def infer_structure(data, depth=0, max_depth=4):
    if depth >= max_depth:
        return "..."

    if isinstance(data, dict):
        return {key: infer_structure(value, depth + 1, max_depth) for key, value in list(data.items())[:20]}

    if isinstance(data, list):
        sample = data[0] if data else None
        return {
            "type": "list",
            "length": len(data),
            "sample": infer_structure(sample, depth + 1, max_depth) if sample is not None else None,
        }

    return type(data).__name__


def get_provider_status():
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    anthropic_ready = bool(anthropic_key)
    openai_ready = bool(openai_key)

    preferred = "Anthropic" if anthropic_ready else "OpenAI" if openai_ready else "Aucun"

    return {
        "anthropic": anthropic_ready,
        "openai": openai_ready,
        "preferred": preferred,
        "global_ready": anthropic_ready or openai_ready,
        "anthropic_masked": f"{anthropic_key[:8]}..." if anthropic_ready else "",
        "openai_masked": f"{openai_key[:8]}..." if openai_ready else "",
    }


def compute_progress():
    cv_exists = CV_PDF_PATH.exists() or CV_TXT_PATH.exists()
    analysis_ready = JOB_DATA_PATH.exists()
    generation_ready = GENERATION_RESULTS_PATH.exists()

    analysis_value = 100 if analysis_ready else 30 if cv_exists else 0
    generation_value = 100 if generation_ready else 25 if analysis_ready else 0

    analysis_label = "Terminée" if analysis_ready else "Prête à lancer" if cv_exists else "En attente du CV"
    generation_label = "Terminée" if generation_ready else "Prête à lancer" if analysis_ready else "En attente de l'analyse"

    return {
        "analysis": {"value": analysis_value, "label": analysis_label},
        "generation": {"value": generation_value, "label": generation_label},
    }


def run_local_command(command, step_key, step_label, extra_env=None):
    rendered_command = " ".join(command)
    st.session_state.last_command_details[step_key] = {"command": rendered_command, "returncode": None}
    add_log(f"Démarrage de l'étape {step_label} avec la commande: {rendered_command}", source=step_label)

    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    try:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
            for key, value in extra_env.items():
                preview = value if key != "JOB_URL" else (value[:80] + "..." if len(value) > 80 else value)
                add_log(f"Variable injectée pour {step_label}: {key}={preview}", source=step_label)

        progress_placeholder.progress(10, text=f"{step_label} : préparation")
        result = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
        progress_placeholder.progress(80, text=f"{step_label} : lecture des sorties")

        st.session_state.last_command_details[step_key] = {
            "command": rendered_command,
            "returncode": result.returncode,
        }

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stdout:
            for line in stdout.splitlines():
                add_log(line, source=step_label)

        if stderr:
            error_level = "WARNING" if result.returncode == 0 else "ERROR"
            for line in stderr.splitlines():
                add_log(line, level=error_level, source=step_label)

        if result.returncode == 0:
            st.session_state.last_action_status[step_key] = "success"
            add_log(f"{step_label} terminée avec succès.", level="SUCCESS", source=step_label)
            progress_placeholder.progress(100, text=f"{step_label} : terminée")
            status_placeholder.success(f"{step_label} terminée avec succès.")
        else:
            st.session_state.last_action_status[step_key] = "error"
            add_log(f"{step_label} a échoué avec le code {result.returncode}.", level="ERROR", source=step_label)
            progress_placeholder.progress(100, text=f"{step_label} : échec")
            status_placeholder.error(f"{step_label} a échoué (code {result.returncode}).")

        st.session_state.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except FileNotFoundError as exc:
        st.session_state.last_action_status[step_key] = "error"
        add_log(f"Commande introuvable pour {step_label}: {exc}", level="ERROR", source=step_label)
        status_placeholder.error(f"Commande introuvable pour {step_label}.")
    except Exception as exc:
        st.session_state.last_action_status[step_key] = "error"
        add_log(f"Erreur inattendue pendant {step_label}: {exc}", level="ERROR", source=step_label)
        status_placeholder.error(f"Erreur inattendue pendant {step_label}: {exc}")


def render_provider_status(provider_status):
    with st.container(border=True):
        st.subheader("État de connexion / configuration IA")

        col1, col2 = st.columns(2)
        with col1:
            if provider_status["anthropic"]:
                st.success("Anthropic : clé détectée, service prêt")
            else:
                st.error("Anthropic : clé absente, service non prêt")

        with col2:
            if provider_status["openai"]:
                st.success("OpenAI : clé détectée, service prêt")
            else:
                st.error("OpenAI : clé absente, service non prêt")

        if provider_status["global_ready"]:
            st.info(f"Fournisseur disponible en priorité : {provider_status['preferred']}")
        else:
            st.warning("Aucun fournisseur IA n'est prêt. Les appels distants échoueront.")

        details_col1, details_col2 = st.columns(2)
        with details_col1:
            st.caption(
                f"Anthropic clé détectée : `{provider_status['anthropic_masked']}`"
                if provider_status["anthropic"]
                else "Anthropic clé détectée : aucune"
            )
        with details_col2:
            st.caption(
                f"OpenAI clé détectée : `{provider_status['openai_masked']}`"
                if provider_status["openai"]
                else "OpenAI clé détectée : aucune"
            )

        st.caption("Vérification basée sur la présence des variables d'environnement `ANTHROPIC_API_KEY` et `OPENAI_API_KEY`. Cela confirme la configuration locale, pas la validité distante de la clé.")


def render_file_status(title, path: Path, description):
    info = get_file_info(path)
    with st.container(border=True):
        st.subheader(title)
        st.caption(description)
        st.code(str(path))

        if info["exists"]:
            st.success("Fichier présent")
            meta_col1, meta_col2 = st.columns(2)
            meta_col1.metric("Taille", f"{info['size']} octets")
            meta_col2.metric("Modifié le", info["modified_at"])
        else:
            st.warning("Fichier absent")


def render_json_panel(title, path: Path):
    data = read_json_file(path)
    summary = summarize_data(data)

    with st.container(border=True):
        st.subheader(title)
        st.caption(str(path))

        col1, col2 = st.columns(2)
        col1.metric("Type", summary["type"])
        col2.metric("Éléments racine", summary["count"])

        if summary["keys"]:
            st.write("Clés principales :", ", ".join(summary["keys"]))

        tab1, tab2 = st.tabs(["Structure", "JSON"])
        with tab1:
            if data is None:
                st.info("Aucune donnée disponible.")
            else:
                st.json(infer_structure(data), expanded=True)
        with tab2:
            if data is None:
                st.info("Le fichier n'existe pas encore.")
            else:
                st.json(data, expanded=False)


def render_logs_panel():
    with st.container(border=True):
        st.subheader("Logs verbeux")
        st.caption("Logs de session du dashboard et sorties stdout/stderr des commandes lancées depuis cette interface.")

        button_col1, button_col2 = st.columns(2)
        if button_col1.button("Actualiser l'interface", use_container_width=True):
            st.session_state.last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            add_log("Rafraîchissement manuel du dashboard.", source="dashboard")
            st.rerun()

        if button_col2.button("Effacer les logs", use_container_width=True):
            st.session_state.dashboard_logs = []
            st.session_state.last_refresh_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            add_log("Historique des logs réinitialisé.", source="dashboard")
            st.rerun()

        if st.session_state.dashboard_logs:
            st.text_area(
                "Console des logs",
                value="\n".join(st.session_state.dashboard_logs[-250:]),
                height=340,
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("Aucun log disponible pour le moment.")

        st.caption(f"Dernier rafraîchissement : {st.session_state.last_refresh_at}")


def render_text_diagrams():
    with st.container(border=True):
        st.subheader("Diagrammes textuels du système")
        st.caption("Vue d'ensemble lisible directement dans le dashboard, sans Mermaid et sans dépendance externe.")

        diagram_col1, diagram_col2 = st.columns(2)

        with diagram_col1:
            st.markdown("**1) Architecture globale**")
            st.code(
                """[Utilisateur]
     |
     v
+-----------------------+
| Dashboard Streamlit   |
| dashboard/app.py      |
+-----------------------+
   |        |        |
   |        |        +--> Lit /output/*.json
   |        |
   |        +--> Lance analyzer/main.py
   |        |
   |        +--> Lance generator/main.py
   |
   +--> Lit /data/cv.pdf ou /data/resume_europass.txt
   +--> Lit variables d'environnement IA

+-------------------+      +-------------------+
| analyzer/main.py  | ---> | /output/job_data  |
+-------------------+      +-------------------+

+-------------------+      +-----------------------------+
| generator/main.py | ---> | /output/generation_results  |
+-------------------+      +-----------------------------+

+-------------------+
| mcp_server/main.py|
+-------------------+
   |
   +--> Expose la logique MCP
   +--> Orchestre des composants/outils
   +--> Dialogue avec services IA externes

+-------------------+      +-------------------+
| Anthropic API     |      | OpenAI API        |
+-------------------+      +-------------------+""",
                language="text",
            )

        with diagram_col2:
            st.markdown("**2) Pipeline d'activité / exécution**")
            st.code(
                """[1] Dépôt du CV
    |
    +--> /data/cv.pdf
    `--> /data/resume_europass.txt

[2] Saisie de JOB_URL dans le dashboard
    |
    v
[3] Bouton "Analyser"
    |
    v
dashboard/app.py
    |
    `--> subprocess -> analyzer/main.py
                     |
                     +--> lit CV + JOB_URL
                     +--> appelle éventuellement un provider IA
                     `--> écrit /output/job_data.json

[4] Contrôle visuel dans le dashboard
    |
    +--> statut fichiers
    +--> structure JSON
    `--> logs d'exécution

[5] Bouton "Générer Europass"
    |
    v
dashboard/app.py
    |
    `--> subprocess -> generator/main.py
                     |
                     +--> lit /output/job_data.json
                     `--> écrit /output/generation_results.json

[6] Restitution finale
    |
    +--> JSON affiché
    +--> progression mise à jour
    `--> historique d'exécution visible""",
                language="text",
            )

        st.markdown("**3) Détail MCP : composants internes et externes**")
        mcp_col1, mcp_col2 = st.columns([1.2, 1])

        with mcp_col1:
            st.code(
                """                    +----------------------------------+
                    |         Clients / Appels           |
                    | dashboard, scripts, outils externes|
                    +----------------+-------------------+
                                     |
                                     v
                         +-----------+------------+
                         |   mcp_server/main.py   |
                         | Point d'entrée MCP     |
                         +-----------+------------+
                                     |
                  +------------------+------------------+
                  |                                     |
                  v                                     v
        +---------+----------+               +----------+---------+
        | Routage requêtes   |               | Gestion contexte   |
        | outils / ressources|               | paramètres / état  |
        +---------+----------+               +----------+---------+
                  |                                     |
                  +------------------+------------------+
                                     |
                                     v
                         +-----------+------------+
                         |  Couche d'orchestration|
                         |  appels métiers / LLM  |
                         +-----------+------------+
                                     |
             +-----------------------+------------------------+
             |                        |                       |
             v                        v                       v
   +---------+---------+   +----------+----------+   +--------+---------+
   | Lecture fichiers  |   | Appels providers IA |   | Sorties / réponses|
   | /data /output     |   | Anthropic / OpenAI  |   | JSON / payload MCP |
   +-------------------+   +---------------------+   +-------------------+""",
                language="text",
            )

        with mcp_col2:
            st.markdown(
                """
- **Composants internes MCP**
  - point d'entrée serveur
  - routage des commandes MCP
  - orchestration métier
  - lecture des fichiers locaux
  - préparation des réponses structurées

- **Dépendances externes**
  - variables d'environnement `ANTHROPIC_API_KEY`
  - variables d'environnement `OPENAI_API_KEY`
  - APIs LLM distantes
  - fichiers montés dans `/data` et `/output`

- **Flux principal**
  1. un client appelle le serveur MCP
  2. le serveur valide la requête
  3. le serveur lit le contexte local utile
  4. le serveur interroge éventuellement un provider IA
  5. le serveur renvoie un résultat structuré
                """
            )

        st.caption("Ces schémas sont documentaires : ils complètent l'observabilité existante du dashboard sans modifier le pipeline.")


def main():
    init_session_state()

    st.title("🚀 Job Bot General")
    st.caption("Dashboard local enrichi pour piloter l'analyse, la génération, la configuration IA et la lecture des données produites.")

    provider_status = get_provider_status()
    progress = compute_progress()

    top_col1, top_col2, top_col3, top_col4 = st.columns(4)
    top_col1.metric("CV disponible", "Oui" if (CV_PDF_PATH.exists() or CV_TXT_PATH.exists()) else "Non")
    top_col2.metric("Analyse disponible", "Oui" if JOB_DATA_PATH.exists() else "Non")
    top_col3.metric("Génération disponible", "Oui" if GENERATION_RESULTS_PATH.exists() else "Non")
    top_col4.metric("IA prête", "Oui" if provider_status["global_ready"] else "Non")

    st.divider()

    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        st.header("Pilotage du pipeline")

        with st.container(border=True):
            st.subheader("Entrées utilisateur")
            job_url = st.text_input("URL de l'offre", value=st.session_state.job_url, placeholder="https://...")
            st.session_state.job_url = job_url

            cv_file = st.file_uploader("CV Europass", type=["txt", "pdf"])

            upload_col1, upload_col2 = st.columns(2)
            if upload_col1.button("Sauvegarder CV", use_container_width=True, disabled=cv_file is None):
                if cv_file is not None:
                    destination = CV_PDF_PATH if cv_file.name.lower().endswith(".pdf") else CV_TXT_PATH
                    save_uploaded_file(cv_file, destination)
                    add_log(f"CV sauvegardé dans {destination}.", level="SUCCESS", source="upload")
                    st.success(f"CV sauvegardé dans {destination.name}.")
                    st.rerun()

            if upload_col2.button("Enregistrer l'URL en session", use_container_width=True, disabled=not job_url.strip()):
                add_log(f"URL d'offre enregistrée dans la session: {job_url}", source="interface")
                st.success("URL enregistrée pour cette session.")

        with st.container(border=True):
            st.subheader("Progression")
            st.write("Analyse")
            st.progress(progress["analysis"]["value"], text=progress["analysis"]["label"])
            st.write("Génération")
            st.progress(progress["generation"]["value"], text=progress["generation"]["label"])

            if st.session_state.last_run_at:
                st.caption(f"Dernière exécution déclenchée depuis le dashboard : {st.session_state.last_run_at}")

        with st.container(border=True):
            st.subheader("Actions")
            st.caption("Les boutons lancent les scripts Python localement dans l'environnement du dashboard, sans backend externe.")

            analysis_disabled = not (CV_PDF_PATH.exists() or CV_TXT_PATH.exists()) or not st.session_state.job_url.strip()
            generation_disabled = not JOB_DATA_PATH.exists()

            action_col1, action_col2 = st.columns(2)

            if action_col1.button("Analyser", use_container_width=True, disabled=analysis_disabled):
                add_log("Préparation de l'analyse demandée depuis l'interface.", source="dashboard")
                add_log(f"Script analyzer détecté: {ANALYZER_SCRIPT_PATH.exists()} ({ANALYZER_SCRIPT_PATH})", source="dashboard")
                run_local_command(
                    [sys.executable, str(ANALYZER_SCRIPT_PATH)],
                    "analyse",
                    "Analyse",
                    extra_env={"JOB_URL": st.session_state.job_url.strip()},
                )
                st.rerun()

            if action_col2.button("Générer Europass", use_container_width=True, disabled=generation_disabled):
                add_log("Préparation de la génération demandée depuis l'interface.", source="dashboard")
                add_log(f"Script generator détecté: {GENERATOR_SCRIPT_PATH.exists()} ({GENERATOR_SCRIPT_PATH})", source="dashboard")
                run_local_command(
                    [sys.executable, str(GENERATOR_SCRIPT_PATH)],
                    "generation",
                    "Génération",
                )
                st.rerun()

            if not (CV_PDF_PATH.exists() or CV_TXT_PATH.exists()):
                st.info("Ajoutez un CV dans `/data` pour activer l'analyse.")
            if not st.session_state.job_url.strip():
                st.warning("Renseignez l'URL de l'offre : sans `JOB_URL`, analyzer termine dans le vide.")
            if generation_disabled:
                st.info("Le fichier `/output/job_data.json` doit exister avant la génération.")

    with right_col:
        render_provider_status(provider_status)

        st.subheader("État local des fichiers")
        render_file_status("CV PDF", CV_PDF_PATH, "Fichier PDF attendu ou déposé via l'interface.")
        render_file_status("CV texte", CV_TXT_PATH, "Version texte éventuellement utilisée par le projet.")
        render_file_status("Données d'analyse", JOB_DATA_PATH, "Sortie produite par `analyzer/main.py`.")
        render_file_status("Résultats de génération", GENERATION_RESULTS_PATH, "Sortie produite par `generator/main.py`.")

    st.divider()

    data_col1, data_col2 = st.columns(2)
    with data_col1:
        render_json_panel("Structure et contenu de `/output/job_data.json`", JOB_DATA_PATH)
    with data_col2:
        render_json_panel("Structure et contenu de `/output/generation_results.json`", GENERATION_RESULTS_PATH)

    st.divider()

    with st.container(border=True):
        st.subheader("Exécution et structure technique")
        exec_col1, exec_col2 = st.columns(2)

        with exec_col1:
            st.write("**Scripts attendus**")
            st.code(
                "\n".join(
                    [
                        f"Analyzer : {ANALYZER_SCRIPT_PATH}",
                        f"Generator : {GENERATOR_SCRIPT_PATH}",
                        f"Python utilisé : {sys.executable}",
                    ]
                )
            )
            st.write("**Variables utiles pour l'analyse**")
            st.code(
                "\n".join(
                    [
                        f"JOB_URL en session : {st.session_state.job_url or '(vide)'}",
                        f"CV texte présent : {CV_TXT_PATH.exists()}",
                        f"CV PDF présent : {CV_PDF_PATH.exists()}",
                        f"job_data.json présent : {JOB_DATA_PATH.exists()}",
                        f"generation_results.json présent : {GENERATION_RESULTS_PATH.exists()}",
                    ]
                )
            )

        with exec_col2:
            st.write("**Dernier statut d'exécution**")
            st.json(
                {
                    "analyse": {
                        "status": st.session_state.last_action_status["analyse"],
                        **st.session_state.last_command_details["analyse"],
                    },
                    "generation": {
                        "status": st.session_state.last_action_status["generation"],
                        **st.session_state.last_command_details["generation"],
                    },
                },
                expanded=True,
            )

    st.divider()
    render_text_diagrams()

    render_logs_panel()

    st.info("Dashboard prêt - Accès : http://localhost:8501")


if __name__ == "__main__":
    main()
