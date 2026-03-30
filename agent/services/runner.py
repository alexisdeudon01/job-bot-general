from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from agent.domain.models import AgentResult, ToolCallRecord
from agent.services.tools import scrape_job
from agent.utils.logging import log

MAX_ITERATIONS = 8
MAX_CV_CHARS = 12000
MAX_TOOL_RESULT_PREVIEW_CHARS = 1000
MAX_FALLBACK_REASONING_CHARS = 2000

ANTHROPIC_TOOLS = [
    {
        "name": "scrape_job",
        "description": "Récupère le contenu textuel brut d'une offre d'emploi à partir de son URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "L'URL de l'offre d'emploi à scraper.",
                }
            },
            "required": ["url"],
        },
    }
]

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "scrape_job",
            "description": "Récupère le contenu textuel brut d'une offre d'emploi à partir de son URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "L'URL de l'offre d'emploi à scraper.",
                    }
                },
                "required": ["url"],
            },
        },
    }
]

SYSTEM_PROMPT = """Tu es un expert en stratégie de carrière. Tu analyses des offres d'emploi et évalues leur adéquation avec le profil d'un candidat.

Pour chaque offre :
1. Utilise l'outil scrape_job pour récupérer le contenu de l'offre
2. Analyse l'adéquation entre l'offre et le profil du candidat
3. Génère une lettre de motivation et un CV adapté si la recommandation est "apply"
4. Retourne une réponse JSON structurée

Format de réponse JSON attendu :
{
  "recommendation": "apply" ou "skip",
  "fit_score": <entier de 0 à 100>,
  "reasoning": "<explication détaillée de l'adéquation>",
  "cover_letter": "<lettre de motivation complète en français>" ou null,
  "adapted_cv": "<adaptation du CV pour ce poste>" ou null
}

Réponds UNIQUEMENT avec ce JSON à la fin, sans texte supplémentaire."""


def build_user_message(job_url: str, cv_text: str) -> str:
    return (
        f"Analyse l'offre d'emploi à l'URL suivante et évalue l'adéquation avec le profil candidat.\n\n"
        f"URL : {job_url}\n\n"
        f"CV du candidat :\n{cv_text[:MAX_CV_CHARS]}\n\n"
        f"Commence par scraper l'offre avec l'outil scrape_job, puis effectue ton analyse."
    )


def execute_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Execute a tool call and return its string result."""
    if tool_name == "scrape_job":
        url = tool_input.get("url", "")
        return scrape_job(url)
    return f"Outil inconnu : {tool_name}"


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object found in LLM response text."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def run_anthropic_agent(client, model_id: str, job_url: str, cv_text: str) -> AgentResult:
    """Run the job-fit agent using Anthropic tool calling."""
    messages: List[Dict[str, Any]] = [{"role": "user", "content": build_user_message(job_url, cv_text)}]
    tool_calls_record: List[ToolCallRecord] = []

    for iteration in range(MAX_ITERATIONS):
        log(f"Itération {iteration + 1}/{MAX_ITERATIONS} de l'agent Anthropic.", "INFO")
        response = client.messages.create(
            model=model_id,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=ANTHROPIC_TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text_parts = [
                block.text
                for block in response.content
                if hasattr(block, "text") and block.text
            ]
            final_text = "\n".join(text_parts)
            parsed = extract_json_from_text(final_text)
            if parsed:
                return AgentResult(
                    job_url=job_url,
                    recommendation=parsed.get("recommendation", "unclear"),
                    fit_score=parsed.get("fit_score"),
                    reasoning=parsed.get("reasoning"),
                    cover_letter=parsed.get("cover_letter"),
                    adapted_cv=parsed.get("adapted_cv"),
                    tool_calls=tool_calls_record,
                    provider="anthropic",
                    model=model_id,
                )
            return AgentResult(
                job_url=job_url,
                recommendation="unclear",
                reasoning=final_text[:MAX_FALLBACK_REASONING_CHARS],
                tool_calls=tool_calls_record,
                provider="anthropic",
                model=model_id,
            )

        if response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_use_blocks:
                tool_name = tool_use.name
                tool_input = tool_use.input or {}
                log(f"Appel outil : {tool_name}({json.dumps(tool_input)[:200]})", "INFO")
                result_text = execute_tool_call(tool_name, tool_input)
                tool_calls_record.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        arguments=tool_input,
                        result={"text": result_text[:MAX_TOOL_RESULT_PREVIEW_CHARS]},
                    )
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_text,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"L'agent Anthropic n'a pas convergé après {MAX_ITERATIONS} itérations.")


def run_openai_agent(client, model_id: str, job_url: str, cv_text: str) -> AgentResult:
    """Run the job-fit agent using OpenAI function calling."""
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(job_url, cv_text)},
    ]
    tool_calls_record: List[ToolCallRecord] = []

    for iteration in range(MAX_ITERATIONS):
        log(f"Itération {iteration + 1}/{MAX_ITERATIONS} de l'agent OpenAI.", "INFO")
        response = client.chat.completions.create(
            model=model_id,
            max_tokens=8000,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            messages=messages,
        )

        choice = response.choices[0]
        message = choice.message

        if choice.finish_reason == "stop":
            final_text = message.content or ""
            parsed = extract_json_from_text(final_text)
            if parsed:
                return AgentResult(
                    job_url=job_url,
                    recommendation=parsed.get("recommendation", "unclear"),
                    fit_score=parsed.get("fit_score"),
                    reasoning=parsed.get("reasoning"),
                    cover_letter=parsed.get("cover_letter"),
                    adapted_cv=parsed.get("adapted_cv"),
                    tool_calls=tool_calls_record,
                    provider="openai",
                    model=model_id,
                )
            return AgentResult(
                job_url=job_url,
                recommendation="unclear",
                reasoning=final_text[:MAX_FALLBACK_REASONING_CHARS],
                tool_calls=tool_calls_record,
                provider="openai",
                model=model_id,
            )

        if choice.finish_reason == "tool_calls":
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in (message.tool_calls or [])
                    ],
                }
            )

            for tool_call in message.tool_calls or []:
                tool_name = tool_call.function.name
                try:
                    tool_input = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_input = {}
                log(f"Appel outil : {tool_name}({json.dumps(tool_input)[:200]})", "INFO")
                result_text = execute_tool_call(tool_name, tool_input)
                tool_calls_record.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        arguments=tool_input,
                        result={"text": result_text[:MAX_TOOL_RESULT_PREVIEW_CHARS]},
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    }
                )

    raise RuntimeError(f"L'agent OpenAI n'a pas convergé après {MAX_ITERATIONS} itérations.")
