import os
import json
import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic
import spacy
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
nlp = spacy.load("fr_core_news_lg")

def scrape(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:30000]

def nlp_clean(text):
    doc = nlp(text.lower())
    clean_tokens = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and len(token.text) > 2]
    entities = [ent.text for ent in doc.ents]
    return {
        "clean_text": " ".join(clean_tokens[:800]),
        "entities": list(set(entities))[:30],
        "keywords": list(set(clean_tokens))[:50]
    }

def deep_cv_analysis(cv_text):
    prompt = f"""
Analyse en profondeur ce CV Europass. Extrait projets, entreprises et arguments forts.

CV :
{cv_text[:20000]}

Retourne UNIQUEMENT un JSON :
{{
  "candidate_strengths": ["..."],
  "enriched_experiences": [{{ "company": "...", "project": "...", "context": "...", "achievements": [...], "arguments_favor": [...] }}],
  "europass_sections": {{ "summary": "...", "skills": [...] }}
}}
"""
    resp = anthropic.messages.create(model="claude-3-5-sonnet-20241022", max_tokens=8000, messages=[{"role": "user", "content": prompt}])
    json_str = resp.content[0].text.strip()
    if json_str.startswith("```json"): json_str = json_str[7:-3].strip()
    return json.loads(json_str)

def create_job_json(url, raw_text, cv_text, nlp_result, cv_analysis):
    prompt = f"""
Analyse l'offre et combine avec l'analyse du CV.

URL: {url}
Offre: {raw_text[:20000]}
NLP: {nlp_result}
CV Analysis: {json.dumps(cv_analysis, ensure_ascii=False)}

Retourne UNIQUEMENT un JSON complet avec "candidate_analysis", "generation_prompts" (incluant europass_cv_prompt).
"""
    response = anthropic.messages.create(model="claude-3-5-sonnet-20241022", max_tokens=9000, messages=[{"role": "user", "content": prompt}])
    json_str = response.content[0].text.strip()
    if json_str.startswith("```json"): json_str = json_str[7:-3].strip()
    return json.loads(json_str)

if __name__ == "__main__":
    url = input("URL de l'offre : ").strip()
    with open("/data/resume_europass.txt", "r", encoding="utf-8") as f:
        cv_text = f.read()

    raw = scrape(url)
    nlp_res = nlp_clean(raw)
    cv_analysis = deep_cv_analysis(cv_text)
    job_json = create_job_json(url, raw, cv_text, nlp_res, cv_analysis)

    with open("/output/job_data.json", "w", encoding="utf-8") as f:
        json.dump(job_json, f, ensure_ascii=False, indent=2)

    print("✅ Analyse terminée")
