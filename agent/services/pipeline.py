from __future__ import annotations

import json
import os
from typing import Optional

from dotenv import load_dotenv

from agent.domain.models import AgentPaths, AgentResult
from agent.services.runner import run_openai_agent
from agent.utils.logging import log


def resolve_openai_model(client) -> str:
    models_page = client.models.list()
    available = [getattr(m, "id", None) for m in models_page.data]
    available = [m for m in available if m]
    if not available:
        raise RuntimeError("Aucun modèle OpenAI disponible.")
    preferred = [m for m in available if "gpt-4o" in m or "gpt-4" in m]
    selected = preferred[0] if preferred else available[0]
    log(f"Modèle OpenAI sélectionné : {selected}", "INFO")
    return selected


def write_result(result: AgentResult, path: str) -> None:
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(result.to_dict(), file, ensure_ascii=False, indent=2)
    log(f"Résultat agent écrit dans {path}.", "INFO")


def run_agent_pipeline(job_url: str, paths: Optional[AgentPaths] = None) -> AgentResult:
    load_dotenv()
    effective_paths = paths or AgentPaths()

    with open(effective_paths.resume_path, "r", encoding="utf-8") as file:
        cv_text = file.read()

    log(
        f"CV chargé ({len(cv_text)} caractères). Démarrage de l'agent pour : {job_url}",
        "INFO",
    )

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY manquante. Configurez cette variable d'environnement."
        )

    from openai import OpenAI

    client = OpenAI(api_key=openai_api_key)
    model_id = resolve_openai_model(client)
    log("Lancement de l'agent avec OpenAI.", "INFO")
    result = run_openai_agent(client, model_id, job_url, cv_text)
    write_result(result, effective_paths.result_path)
    return result
