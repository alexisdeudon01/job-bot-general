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
        "Respecte strictement les informations fournies dans le contexte et le CV original.",
        "N'ajoute aucune question.",
        "N'ajoute aucun commentaire, avertissement, note, préface ou postface.",
        "N'indique pas que des informations manquent.",
        "N'utilise aucun placeholder de type [Nom], [Téléphone], [Email], [Ville] ou équivalent.",
        "N'invente pas d'expérience, de diplôme, de compétence, de certification, de langue, de date, de lieu, d'entreprise ou de coordonnées non présents dans les données.",
        "Si une information est absente, laisse la section sobre, neutre et professionnelle sans signaler l'absence.",
        "Le résultat doit être directement exploitable comme CV final.",
        "Utilise une structure claire de CV Europass avec des rubriques cohérentes.",
        "Mets fortement en avant les éléments du profil les plus pertinents pour l'offre visée.",
        "Reformule de manière professionnelle, précise et crédible, sans exagération ni contenu fictif.",
        "Conserve une tonalité formelle, concise et orientée recrutement.",
        "Retourne uniquement le contenu final du CV, sans balises Markdown, sans bloc de code et sans texte hors CV.",
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
        "Retourne uniquement le CV final rédigé, prêt à être utilisé, au format texte clair.",
    ]

    return "\n".join(prompt_sections)
