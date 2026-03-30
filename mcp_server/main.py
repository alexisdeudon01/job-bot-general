import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

import pdfplumber
import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

mcp = FastMCP("job-bot-mcp")

PROMPT_CHAR_PER_TOKEN_ESTIMATE = 4
PROMPT_TOKEN_SAFETY_MARGIN = 500
MIN_INPUT_TOKEN_BUDGET = 1200
DEFAULT_ANTHROPIC_MAX_TOKENS = 2200
DEFAULT_OPENAI_MAX_TOKENS = 1800
MAX_OPENAI_MODEL_ATTEMPTS = 12

EUROPASS_SECTION_HINTS = {
    "personal_information": [
        "informations personnelles",
        "personal information",
        "coordonnees",
        "coordonnées",
        "contact",
    ],
    "work_experience": ["experience professionnelle", "expérience professionnelle", "work experience"],
    "education": ["education et formation", "éducation et formation", "education", "formation"],
    "skills": ["competences", "compétences", "skills", "competences linguistiques", "langues"],
    "projects": ["projets", "projects"],
    "certifications": ["certifications", "licenses", "licences"],
    "summary": ["profil", "resume", "résumé", "a propos", "à propos"],
}

EUROPASS_JSON_FORMAT = "europass_cv_json"
EUROPASS_JSON_VERSION = "1.0"


class MCPError(RuntimeError):
    """MCP functional error."""


def normalize_text(text):
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text)


def safe_json_loads(value, field_name):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            raise MCPError(f"`{field_name}` doit être un JSON objet")
        except json.JSONDecodeError as error:
            raise MCPError(f"`{field_name}` n'est pas un JSON valide: {error}") from error
    raise MCPError(f"`{field_name}` doit être un objet JSON ou une string JSON")


def extract_first_json_object(text):
    if not isinstance(text, str):
        return None

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            parsed, _end_index = decoder.raw_decode(text[index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def safe_extract_json_block(value):
    if isinstance(value, dict):
        return value

    if not isinstance(value, str) or not value.strip():
        return None

    raw_value = value.strip()

    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    code_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_value, re.DOTALL)
    if code_block_match:
        code_block_content = code_block_match.group(1).strip()
        parsed = extract_first_json_object(code_block_content)
        if parsed is not None:
            return parsed

    return extract_first_json_object(raw_value)


def resolve_file_path(file_path):
    if not file_path:
        raise MCPError("Le chemin de fichier est vide")

    if os.path.isabs(file_path):
        resolved = file_path
    else:
        resolved = os.path.abspath(file_path)

    if not os.path.exists(resolved):
        raise MCPError(f"Fichier introuvable: {resolved}")

    return resolved


def resolve_anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise MCPError("ANTHROPIC_API_KEY manquante")
    return Anthropic(api_key=api_key)


def resolve_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise MCPError("OPENAI_API_KEY manquante")
    return OpenAI(api_key=api_key)


def extract_positive_int_attribute(obj, attribute_names):
    for attribute_name in attribute_names:
        value = getattr(obj, attribute_name, None)
        if isinstance(value, int) and value > 0:
            return value
    return None


def resolve_anthropic_model_info(client):
    models_page = client.models.list(limit=100)
    available_models = [model for model in models_page.data if getattr(model, "id", None)]

    if not available_models:
        raise MCPError("Aucun modèle Anthropic disponible")

    selected_model = available_models[0]
    return {
        "id": selected_model.id,
        "output_token_limit": extract_positive_int_attribute(
            selected_model,
            ("output_token_limit", "max_output_tokens", "max_tokens", "max_completion_tokens"),
        ),
        "input_token_limit": extract_positive_int_attribute(
            selected_model,
            ("input_token_limit", "max_input_tokens", "context_window", "context_length"),
        ),
    }


def resolve_openai_model_id(client):
    models_page = client.models.list()
    available_models = [getattr(model, "id", None) for model in models_page.data]
    available_models = [model_id for model_id in available_models if model_id]

    if not available_models:
        raise MCPError("Aucun modèle OpenAI disponible")

    return available_models[0]


def resolve_openai_model_candidates(client):
    models_page = client.models.list()
    candidates = [getattr(model, "id", None) for model in models_page.data]
    candidates = [model_id for model_id in candidates if model_id]
    if not candidates:
        raise MCPError("Aucun modèle OpenAI disponible")

    excluded_keywords = (
        "embedding",
        "moderation",
        "whisper",
        "tts",
        "audio",
        "transcribe",
        "image",
        "realtime",
    )

    filtered_candidates = []
    for model_id in candidates:
        lower_model_id = model_id.lower()
        if any(keyword in lower_model_id for keyword in excluded_keywords):
            continue
        filtered_candidates.append(model_id)

    return filtered_candidates or candidates


def infer_openai_context_limit_from_error(error):
    error_message = str(error)
    match = re.search(r"maximum context length is\s*(\d+)\s*tokens", error_message, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def is_openai_model_or_endpoint_error(error):
    error_message = str(error).lower()
    patterns = (
        "not supported",
        "does not support",
        "unsupported",
        "not a chat model",
        "invalid_request_error",
        "unknown parameter",
        "context_length_exceeded",
    )
    return any(pattern in error_message for pattern in patterns)


def call_openai_with_adaptive_prompt(client, prompt, requested_max_tokens, system_prompt):
    model_candidates = resolve_openai_model_candidates(client)[:MAX_OPENAI_MODEL_ATTEMPTS]
    last_error = None

    for model_id in model_candidates:
        try:
            response = client.chat.completions.create(
                model=model_id,
                temperature=0.2,
                max_tokens=requested_max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            return response, model_id, requested_max_tokens
        except Exception as error:
            last_error = error
            context_limit = infer_openai_context_limit_from_error(error)
            if context_limit:
                adapted_prompt = adapt_prompt_to_input_limit(
                    prompt=prompt,
                    input_token_limit=context_limit,
                    reserved_output_tokens=requested_max_tokens,
                )
                try:
                    response = client.chat.completions.create(
                        model=model_id,
                        temperature=0.2,
                        max_tokens=requested_max_tokens,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": adapted_prompt},
                        ],
                    )
                    return response, model_id, requested_max_tokens
                except Exception as retry_error:
                    last_error = retry_error

            if is_openai_model_or_endpoint_error(error):
                continue

            raise

    raise MCPError(f"Aucun modèle OpenAI exploitable en chat.completions: {last_error}")


def infer_anthropic_max_tokens_from_error(error):
    error_message = str(error)
    match = re.search(r"max_tokens:\s*\d+\s*>\s*(\d+)", error_message)
    if match:
        return int(match.group(1))
    return None


def adapt_prompt_to_input_limit(prompt, input_token_limit, reserved_output_tokens):
    if not input_token_limit:
        return prompt

    allowed_input_tokens = max(
        MIN_INPUT_TOKEN_BUDGET,
        input_token_limit - reserved_output_tokens - PROMPT_TOKEN_SAFETY_MARGIN,
    )
    max_chars = allowed_input_tokens * PROMPT_CHAR_PER_TOKEN_ESTIMATE

    if len(prompt) <= max_chars:
        return prompt

    return (
        prompt[:max_chars]
        + "\n\n[NOTE TECHNIQUE] Prompt tronqué automatiquement pour respecter la limite de contexte du modèle."
    )


def extract_anthropic_text(response):
    text_parts = []
    for block in getattr(response, "content", []) or []:
        block_text = getattr(block, "text", None)
        if isinstance(block_text, str) and block_text.strip():
            text_parts.append(block_text)

    if not text_parts:
        raise MCPError("Réponse Anthropic sans contenu textuel exploitable")

    return "\n".join(text_parts)


def call_anthropic_with_adaptive_tokens(client, model_info, prompt, requested_max_tokens):
    model_name = model_info["id"]
    output_limit = model_info.get("output_token_limit")
    effective_max_tokens = min(requested_max_tokens, output_limit) if output_limit else requested_max_tokens
    adapted_prompt = adapt_prompt_to_input_limit(
        prompt=prompt,
        input_token_limit=model_info.get("input_token_limit"),
        reserved_output_tokens=effective_max_tokens,
    )

    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=effective_max_tokens,
            messages=[{"role": "user", "content": adapted_prompt}],
        )
        return response, effective_max_tokens
    except Exception as error:
        allowed_max_tokens = infer_anthropic_max_tokens_from_error(error)
        if not allowed_max_tokens:
            raise

        adapted_prompt = adapt_prompt_to_input_limit(
            prompt=prompt,
            input_token_limit=model_info.get("input_token_limit"),
            reserved_output_tokens=allowed_max_tokens,
        )
        response = client.messages.create(
            model=model_name,
            max_tokens=allowed_max_tokens,
            messages=[{"role": "user", "content": adapted_prompt}],
        )
        return response, allowed_max_tokens


def detect_europass_sections(full_text):
    lines = [line.strip() for line in (full_text or "").splitlines() if line.strip()]
    sections = {key: [] for key in EUROPASS_SECTION_HINTS}
    current_section = "summary"

    for line in lines:
        normalized_line = normalize_text(line)
        matched_section = None
        for section_name, hints in EUROPASS_SECTION_HINTS.items():
            if any(hint in normalized_line for hint in hints):
                matched_section = section_name
                break

        if matched_section:
            current_section = matched_section
            continue

        sections[current_section].append(line)

    return {name: "\n".join(values).strip() for name, values in sections.items()}


def extract_job_signals(text):
    normalized_text = text or ""
    emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", normalized_text)))
    phones = sorted(set(re.findall(r"(?:\+\d{1,3}[\s.-]?)?(?:\d[\s.-]?){8,}", normalized_text)))

    salary_patterns = [
        r"\b\d{2,3}\s?000\s?(?:€|eur|euros?)\b",
        r"\b(?:salaire|remuneration|rémunération)\b.{0,40}\b\d+\b",
    ]
    salary_mentions = []
    for pattern in salary_patterns:
        salary_mentions.extend(re.findall(pattern, normalized_text, flags=re.IGNORECASE))

    return {
        "emails": emails[:20],
        "phones": [phone.strip() for phone in phones[:20]],
        "salary_mentions": salary_mentions[:20],
    }


def find_first_match(patterns, text, flags=re.IGNORECASE):
    for pattern in patterns:
        match = re.search(pattern, text or "", flags)
        if match:
            return match.group(1).strip()
    return None


def extract_lines(section_text):
    return [line.strip("•- \t") for line in (section_text or "").splitlines() if line.strip()]


def extract_personal_information(full_text, personal_section):
    lines = extract_lines(personal_section)
    email = find_first_match([r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"], full_text)
    phone = find_first_match([r"((?:\+\d{1,3}[\s.-]?)?(?:\d[\s.-]?){8,})"], full_text)
    linkedin = find_first_match([r"(https?://(?:www\.)?linkedin\.com/[^\s]+)"], full_text)
    website = find_first_match([r"(https?://[^\s]+)"], full_text)

    full_name = None
    for line in lines[:8]:
        if email and email.lower() in line.lower():
            continue
        if phone and phone in line:
            continue
        if len(line.split()) >= 2 and len(line) <= 80 and not any(char.isdigit() for char in line):
            full_name = line
            break

    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "location": {
            "full_address": None,
            "city": None,
            "country": None,
        },
        "nationality": None,
        "date_of_birth": None,
        "digital_presence": [value for value in [linkedin, website] if value],
        "raw_text": personal_section.strip(),
    }


def extract_headline(summary_section):
    lines = extract_lines(summary_section)
    if not lines:
        return {"title": None, "summary": None}

    if len(lines) == 1:
        return {"title": None, "summary": lines[0]}

    return {
        "title": lines[0],
        "summary": "\n".join(lines[1:]).strip() or lines[0],
    }


def extract_list_entries(section_text, default_title_key):
    lines = extract_lines(section_text)
    entries = []
    current = []

    for line in lines:
        if re.search(r"\b(19|20)\d{2}\b", line) and current:
            entries.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        entries.append("\n".join(current).strip())

    normalized_entries = []
    for raw_entry in entries:
        entry_lines = [line.strip() for line in raw_entry.splitlines() if line.strip()]
        if not entry_lines:
            continue

        normalized_entries.append(
            {
                default_title_key: entry_lines[0],
                "description": "\n".join(entry_lines[1:]).strip() or None,
                "raw_text": raw_entry,
            }
        )

    return normalized_entries


def extract_work_experience(section_text):
    base_entries = extract_list_entries(section_text, "position")
    normalized = []
    for entry in base_entries:
        normalized.append(
            {
                "position": entry.get("position"),
                "employer": None,
                "location": None,
                "start_date": None,
                "end_date": None,
                "is_current": False,
                "description": entry.get("description"),
                "achievements": [],
                "raw_text": entry.get("raw_text"),
            }
        )
    return normalized


def extract_education(section_text):
    base_entries = extract_list_entries(section_text, "title")
    normalized = []
    for entry in base_entries:
        normalized.append(
            {
                "title": entry.get("title"),
                "institution": None,
                "start_date": None,
                "end_date": None,
                "description": entry.get("description"),
                "raw_text": entry.get("raw_text"),
            }
        )
    return normalized


def extract_skills(section_text):
    lines = extract_lines(section_text)
    return {
        "digital_skills": [{"name": line, "level": None} for line in lines],
        "communication_skills": [],
        "organisational_skills": [],
        "job_related_skills": [],
        "other_skills": [],
        "driving_licences": [],
        "raw_text": section_text.strip(),
    }


def extract_languages(section_text):
    lines = extract_lines(section_text)
    languages = []
    for line in lines:
        languages.append(
            {
                "language": line,
                "overall": None,
                "listening": None,
                "reading": None,
                "spoken_interaction": None,
                "spoken_production": None,
                "writing": None,
            }
        )
    return languages


def build_europass_cv_json(pdf_path, source_info, full_text, sections):
    personal_section = sections.get("personal_information", "")
    summary_section = sections.get("summary", "")
    work_section = sections.get("work_experience", "")
    education_section = sections.get("education", "")
    skills_section = sections.get("skills", "")
    projects_section = sections.get("projects", "")
    certifications_section = sections.get("certifications", "")

    return {
        "format": EUROPASS_JSON_FORMAT,
        "version": EUROPASS_JSON_VERSION,
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "parser": "job-bot-mcp",
            "schema": "internal-europass-structured-json",
        },
        "personal_information": extract_personal_information(full_text, personal_section),
        "headline": extract_headline(summary_section),
        "work_experience": extract_work_experience(work_section),
        "education_and_training": extract_education(education_section),
        "skills": extract_skills(skills_section),
        "languages": extract_languages(skills_section),
        "projects": extract_list_entries(projects_section, "title"),
        "certifications": extract_list_entries(certifications_section, "title"),
        "publications": [],
        "volunteering": [],
        "digital_presence": extract_personal_information(full_text, personal_section).get("digital_presence", []),
        "additional_information": {
            "summary": None,
            "references": [],
            "annexes": [],
        },
        "attachments": [],
        "source_document": {
            "file_path": pdf_path,
            "file_type": "application/pdf",
            "page_count": source_info.get("page_count"),
            "file_size_bytes": source_info.get("file_size_bytes"),
            "extraction_method": "pdf_to_structured_json",
        },
        "raw_sections": sections,
        "raw_text_excerpt": full_text[:20000],
    }


def build_strategy_prompt(cv_data, job_data, objective):
    return (
        "Tu es un assistant carrière senior.\n"
        "Objectif: produire un plan exploitable basé sur le CV structuré et l'offre structurée.\n"
        "Use-cases visés: cover letter, améliorations CV, enquête entreprise, compréhension des besoins, plan d'actions.\n"
        "Contraintes:\n"
        "- Répondre en français\n"
        "- Structurer la réponse en JSON strict\n"
        "- Ne pas inventer de faits non présents\n"
        "- Si info absente: indiquer `insufficient_data`\n\n"
        "JSON attendu:\n"
        "{\n"
        "  \"cover_letter_draft\": \"...\",\n"
        "  \"cv_improvements\": [\"...\"],\n"
        "  \"company_investigation\": {\"known\": [\"...\"], \"to_verify\": [\"...\"]},\n"
        "  \"role_needs\": {\"must_have\": [\"...\"], \"nice_to_have\": [\"...\"], \"risks\": [\"...\"]},\n"
        "  \"action_plan_7_days\": [\"...\"]\n"
        "}\n\n"
        f"OBJECTIF UTILISATEUR:\n{objective}\n\n"
        f"CV_JSON:\n{json.dumps(cv_data, ensure_ascii=False)}\n\n"
        f"JOB_JSON:\n{json.dumps(job_data, ensure_ascii=False)}"
    )


@mcp.tool()
def europass_pdf_to_json(pdf_path: str) -> dict:
    """Convertit un CV Europass PDF en JSON structuré (sections + métadonnées de mise en page)."""
    resolved_path = resolve_file_path(pdf_path)

    reader = PdfReader(resolved_path)
    page_count = len(reader.pages)
    pages = []

    for page_index, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        pages.append(
            {
                "page": page_index,
                "chars": len(page_text),
                "text": page_text,
            }
        )

    with pdfplumber.open(resolved_path) as pdf_doc:
        layout = []
        for page_index, page in enumerate(pdf_doc.pages, start=1):
            words = page.extract_words() or []
            layout.append(
                {
                    "page": page_index,
                    "width": page.width,
                    "height": page.height,
                    "word_count": len(words),
                    "sample_words": words[:25],
                }
            )

    full_text = "\n\n".join(page["text"] for page in pages if page["text"]).strip()
    sections = detect_europass_sections(full_text)

    return {
        "source": {
            "pdf_path": resolved_path,
            "page_count": page_count,
            "file_size_bytes": os.path.getsize(resolved_path),
        },
        "structure": {
            "sections": sections,
            "pages": [{"page": page["page"], "chars": page["chars"]} for page in pages],
            "layout": layout,
        },
        "raw": {
            "text_excerpt": full_text[:20000],
            "total_chars": len(full_text),
        },
    }


@mcp.tool()
def europass_pdf_to_structured_json(pdf_path: str = "data/cv.pdf") -> dict:
    """Convertit un CV Europass PDF en JSON métier structuré adapté au pipeline."""
    raw_pdf_json = europass_pdf_to_json(pdf_path=pdf_path)
    source_info = raw_pdf_json.get("source", {})
    sections = raw_pdf_json.get("structure", {}).get("sections", {})
    full_text = raw_pdf_json.get("raw", {}).get("text_excerpt", "")

    return build_europass_cv_json(
        pdf_path=source_info.get("pdf_path", resolve_file_path(pdf_path)),
        source_info=source_info,
        full_text=full_text,
        sections=sections,
    )


@mcp.tool()
def job_url_to_json(url: str, timeout_seconds: int = 20) -> dict:
    """Convertit une URL d'offre d'emploi en JSON structuré (contenu + signaux utiles)."""
    if not url or not url.strip():
        raise MCPError("L'URL est vide")

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    response = requests.get(url.strip(), headers=headers, timeout=timeout_seconds)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    meta_description = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag:
        meta_description = (desc_tag.get("content") or "").strip()

    headings = {
        "h1": [h.get_text(" ", strip=True) for h in soup.find_all("h1")][:20],
        "h2": [h.get_text(" ", strip=True) for h in soup.find_all("h2")][:40],
        "h3": [h.get_text(" ", strip=True) for h in soup.find_all("h3")][:60],
    }

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    paragraphs = [p for p in paragraphs if p][:200]

    list_items = [li.get_text(" ", strip=True) for li in soup.find_all("li")]
    list_items = [li for li in list_items if li][:250]

    table_rows = []
    for table in soup.find_all("table")[:10]:
        for tr in table.find_all("tr")[:30]:
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
            if cells:
                table_rows.append(cells)

    cleaned_text = soup.get_text("\n", strip=True)
    cleaned_text = re.sub(r"\n{2,}", "\n", cleaned_text)

    parsed_url = urlparse(url)

    return {
        "source": {
            "url": url,
            "domain": parsed_url.netloc,
            "status_code": response.status_code,
        },
        "structure": {
            "title": title,
            "meta_description": meta_description,
            "headings": headings,
            "paragraphs": paragraphs,
            "list_items": list_items,
            "table_rows": table_rows,
        },
        "signals": extract_job_signals(cleaned_text),
        "raw": {
            "text_excerpt": cleaned_text[:25000],
            "total_chars": len(cleaned_text),
        },
    }


@mcp.tool()
def career_strategy_openai(cv_json: str, job_json: str, objective: str = "cover letter + amélioration CV + enquête entreprise + besoins poste") -> dict:
    """Analyse carrière via OpenAI à partir d'un CV JSON et d'une offre JSON."""
    cv_data = safe_json_loads(cv_json, "cv_json")
    job_data = safe_json_loads(job_json, "job_json")

    client = resolve_openai_client()
    prompt = build_strategy_prompt(cv_data=cv_data, job_data=job_data, objective=objective)

    response, model_id, used_max_tokens = call_openai_with_adaptive_prompt(
        client=client,
        prompt=prompt,
        requested_max_tokens=DEFAULT_OPENAI_MAX_TOKENS,
        system_prompt="Tu es un coach carrière expert, précis et orienté impact.",
    )

    text = response.choices[0].message.content or ""
    return {
        "provider": "openai",
        "model": model_id,
        "used_max_tokens": used_max_tokens,
        "output": text,
    }


@mcp.tool()
def career_strategy_anthropic(cv_json: str, job_json: str, objective: str = "cover letter + amélioration CV + enquête entreprise + besoins poste") -> dict:
    """Analyse carrière via Anthropic à partir d'un CV JSON et d'une offre JSON."""
    cv_data = safe_json_loads(cv_json, "cv_json")
    job_data = safe_json_loads(job_json, "job_json")

    client = resolve_anthropic_client()
    model_info = resolve_anthropic_model_info(client)

    prompt = build_strategy_prompt(cv_data=cv_data, job_data=job_data, objective=objective)

    response, used_max_tokens = call_anthropic_with_adaptive_tokens(
        client=client,
        model_info=model_info,
        prompt=prompt,
        requested_max_tokens=DEFAULT_ANTHROPIC_MAX_TOKENS,
    )
    text = extract_anthropic_text(response)

    return {
        "provider": "anthropic",
        "model": model_info["id"],
        "used_max_tokens": used_max_tokens,
        "output": text,
    }


@mcp.tool()
def career_strategy_dual(cv_json: str, job_json: str, objective: str = "cover letter + amélioration CV + enquête entreprise + besoins poste") -> dict:
    """Exécute l'analyse carrière chez OpenAI et Anthropic et renvoie les deux sorties."""
    results = {}

    try:
        results["openai"] = career_strategy_openai(cv_json=cv_json, job_json=job_json, objective=objective)
    except Exception as error:
        results["openai"] = {"status": "error", "error": str(error)}

    try:
        results["anthropic"] = career_strategy_anthropic(cv_json=cv_json, job_json=job_json, objective=objective)
    except Exception as error:
        results["anthropic"] = {"status": "error", "error": str(error)}

    return results


@mcp.tool()
def career_pipeline_from_pdf_and_url(
    pdf_path: str,
    job_url: str,
    objective: str = "cover letter + amélioration CV + enquête entreprise + besoins poste",
    output_path: str = "/output/mcp_pipeline_result.json",
    save_to_file: bool = True,
) -> dict:
    """
    Pipeline complet:
    1) Convertit CV Europass PDF -> JSON
    2) Convertit URL offre -> JSON
    3) Lance OpenAI + Anthropic
    4) Retourne un pack final (et optionnellement l'écrit sur disque)
    """

    cv_data = europass_pdf_to_structured_json(pdf_path=pdf_path)
    job_data = job_url_to_json(url=job_url)

    dual_results = career_strategy_dual(
        cv_json=json.dumps(cv_data, ensure_ascii=False),
        job_json=json.dumps(job_data, ensure_ascii=False),
        objective=objective,
    )

    openai_result = dual_results.get("openai", {}) if isinstance(dual_results, dict) else {}
    anthropic_result = dual_results.get("anthropic", {}) if isinstance(dual_results, dict) else {}

    openai_output = openai_result.get("output") if isinstance(openai_result, dict) else None
    anthropic_output = anthropic_result.get("output") if isinstance(anthropic_result, dict) else None

    normalized = {
        "openai_json": safe_extract_json_block(openai_output),
        "anthropic_json": safe_extract_json_block(anthropic_output),
    }

    providers_status = {
        "openai": "success" if isinstance(openai_result, dict) and openai_result.get("output") else "error",
        "anthropic": "success" if isinstance(anthropic_result, dict) and anthropic_result.get("output") else "error",
    }

    final_pack = {
        "meta": {
            "tool": "career_pipeline_from_pdf_and_url",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "objective": objective,
            "providers_status": providers_status,
        },
        "inputs": {
            "pdf_path": resolve_file_path(pdf_path),
            "job_url": job_url,
        },
        "cv_json": cv_data,
        "job_json": job_data,
        "llm_raw": dual_results,
        "llm_normalized": normalized,
        "next_steps": [
            "Vérifier la factualité des éléments d'enquête entreprise avant envoi de candidature.",
            "Relire et personnaliser la cover letter avec les faits les plus différenciants du CV.",
            "Intégrer les améliorations CV prioritaires avant candidature finale.",
        ],
    }

    if save_to_file:
        resolved_output_path = output_path if os.path.isabs(output_path) else os.path.abspath(output_path)
        output_directory = os.path.dirname(resolved_output_path)
        if output_directory:
            os.makedirs(output_directory, exist_ok=True)
        with open(resolved_output_path, "w", encoding="utf-8") as output_file:
            json.dump(final_pack, output_file, ensure_ascii=False, indent=2)
        final_pack["meta"]["saved_to"] = resolved_output_path

    return final_pack


if __name__ == "__main__":
    mcp.run()
