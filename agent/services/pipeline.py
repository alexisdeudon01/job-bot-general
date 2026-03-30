from __future__ import annotations

import json
import os
from typing import Optional

from dotenv import load_dotenv

from agent.domain.models import AgentPaths, AgentResult
from agent.services.runner import run_anthropic_agent, run_openai_agent
from agent.utils.logging import log

ANTHROPIC_BLOCKED_MODELS = {
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-latest",
}


def resolve_anthropic_model(client) -> str:
    models_page = client.models.list(limit=100)
    available = [
        m
        for m in models_page.data
        if getattr(m, "id", None) and m.id not in ANTHROPIC_BLOCKED_MODELS
    ]
    if not available:
        raise RuntimeError("Aucun modèle Anthropic disponible.")
    log(f"Modèle Anthropic sélectionné : {available[0].id}", "INFO")
    return available[0].id


def resolve_openai_model(client) -> str:
    models_page = client.models.list()
    available = [getattr(m, "id", None) for m in models_page.data]
    available = [m for m in available if m]
    if not available:
        raise RuntimeError("Aucun modèle OpenAI disponible.")
    log(f"Modèle OpenAI sélectionné : {available[0]}", "INFO")
    return available[0]


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

    log(f"CV chargé ({len(cv_text)} caractères). Démarrage de l'agent pour : {job_url}", "INFO")

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if anthropic_api_key:
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=anthropic_api_key)
            model_id = resolve_anthropic_model(client)
            log("Lancement de l'agent avec Anthropic.", "INFO")
            result = run_anthropic_agent(client, model_id, job_url, cv_text)
            write_result(result, effective_paths.result_path)
            return result
        except Exception as error:
            log(f"Échec de l'agent Anthropic : {error}. Bascule vers OpenAI.", "WARN")

    if openai_api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_api_key)
            model_id = resolve_openai_model(client)
            log("Lancement de l'agent avec OpenAI.", "INFO")
            result = run_openai_agent(client, model_id, job_url, cv_text)
            write_result(result, effective_paths.result_path)
            return result
        except Exception as error:
            log(f"Échec de l'agent OpenAI : {error}.", "ERREUR")
            raise

    raise RuntimeError("Aucune clé API disponible (ANTHROPIC_API_KEY ou OPENAI_API_KEY).")
