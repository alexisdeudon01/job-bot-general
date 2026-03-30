import json
from typing import Any, Dict


def build_generation_prompt(job_data: Dict[str, Any], original_cv: str) -> str:
    candidate_analysis = job_data.get("candidate_analysis", {})
    generation_prompts = job_data.get("generation_prompts", {})

    base_prompt = generation_prompts.get(
        "europass_cv_prompt",
        "Adapte ce CV au format Europass structuré",
    )

    prompt_sections = [
        "Tu dois produire directement un CV Europass complet en français.",
        "N'ajoute aucune question.",
        "N'indique pas que des informations manquent.",
        "Si certaines données sont absentes, complète de manière professionnelle et cohérente.",
        "",
        "=== CONTEXTE OFFRE ET CANDIDAT ===",
        json.dumps(
            {
                "candidate_analysis": candidate_analysis,
                "generation_prompts": generation_prompts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "=== INSTRUCTION CIBLE ===",
        base_prompt,
        "",
        "=== CV ORIGINAL ===",
        original_cv,
        "",
        "=== FORMAT ATTENDU ===",
        "Retourne uniquement le CV final rédigé, prêt à être utilisé.",
    ]

    return "\n".join(prompt_sections)