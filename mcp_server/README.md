# MCP Server — job-bot-general

Serveur MCP dédié au pipeline carrière, avec intégrations directes OpenAI et Anthropic.

## Outils inclus

- `europass_pdf_to_json(pdf_path)`
  - Lit un PDF Europass
  - Extrait texte + sections heuristiques + éléments de structure de page
  - Sert de couche brute/debug

- `europass_pdf_to_structured_json(pdf_path="data/cv.pdf")`
  - Lit un PDF Europass
  - Retourne un JSON CV structuré au format interne `europass_cv_json`
  - Extrait les sections principales : identité, résumé, expériences, formations, compétences, langues, projets, certifications

- `job_url_to_json(url, timeout_seconds=20)`
  - Scrape une offre d'emploi depuis URL
  - Renvoie un JSON structuré (title, headings, paragraphs, list_items, signaux)

- `career_strategy_openai(cv_json, job_json, objective=...)`
  - Utilise OpenAI (modèle détecté dynamiquement via API)

- `career_strategy_anthropic(cv_json, job_json, objective=...)`
  - Utilise Anthropic (modèle détecté dynamiquement via API)
  - Adapte `max_tokens` et le prompt selon les limites modèle

- `career_strategy_dual(cv_json, job_json, objective=...)`
  - Exécute OpenAI + Anthropic et renvoie les deux sorties

- `career_pipeline_from_pdf_and_url(pdf_path, job_url, objective=..., output_path=..., save_to_file=True)`
  - Pipeline complet prêt à l'emploi
  - Convertit le PDF CV en JSON structuré Europass
  - Convertit l'URL de job vacancy en JSON
  - Exécute OpenAI + Anthropic
  - Retourne un pack final (raw + normalisé) et peut l'écrire dans un fichier JSON

## Variables d'environnement

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

## Lancement local

```bash
cd mcp_server
pip install -r requirements.txt
python main.py
```

## Lancement Docker (profil compose)

```bash
docker compose --profile mcp up --build mcp
```

Le serveur MCP tourne en mode stdio.

## Format JSON CV cible

```json
{
  "format": "europass_cv_json",
  "version": "1.0",
  "metadata": {
    "created_at": "2026-03-30T15:00:00Z",
    "parser": "job-bot-mcp",
    "schema": "internal-europass-structured-json"
  },
  "personal_information": {
    "full_name": "Jean Dupont",
    "email": "jean.dupont@example.com",
    "phone": "+33 6 12 34 56 78",
    "location": {
      "full_address": null,
      "city": null,
      "country": null
    },
    "nationality": null,
    "date_of_birth": null,
    "digital_presence": ["https://www.linkedin.com/in/jean-dupont"],
    "raw_text": "..."
  },
  "headline": {
    "title": "Ingénieur cybersécurité",
    "summary": "Résumé professionnel..."
  },
  "work_experience": [],
  "education_and_training": [],
  "skills": {
    "digital_skills": [],
    "communication_skills": [],
    "organisational_skills": [],
    "job_related_skills": [],
    "other_skills": [],
    "driving_licences": [],
    "raw_text": "..."
  },
  "languages": [],
  "projects": [],
  "certifications": [],
  "publications": [],
  "volunteering": [],
  "digital_presence": [],
  "additional_information": {
    "summary": null,
    "references": [],
    "annexes": []
  },
  "attachments": [],
  "source_document": {
    "file_path": "data/cv.pdf",
    "file_type": "application/pdf",
    "page_count": 1,
    "file_size_bytes": 12345,
    "extraction_method": "pdf_to_structured_json"
  },
  "raw_sections": {},
  "raw_text_excerpt": "..."
}
```

## Exemple de flux cible

1. Appeler `career_pipeline_from_pdf_and_url` avec :
  - `pdf_path` : chemin du CV Europass PDF
  - `job_url` : URL de l'offre
2. Récupérer la sortie :
  - `cv_json`
  - `job_json`
  - `llm_raw` (OpenAI + Anthropic)
  - `llm_normalized` (si JSON extractible)
3. Utiliser ce pack pour finaliser cover letter, plan d'amélioration CV et stratégie de candidature.
