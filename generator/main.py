import os
import json
from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open("/output/job_data.json", "r", encoding="utf-8") as f:
    job_data = json.load(f)

original_cv = open("/data/resume_europass.txt", "r", encoding="utf-8").read()

def generate_europass(provider="anthropic"):
    prompt = job_data["generation_prompts"].get("europass_cv_prompt", "Adapte ce CV au format Europass structuré") + f"\n\nCV original :\n{original_cv}"
    if provider == "anthropic":
        resp = anthropic.messages.create(model="claude-3-5-sonnet-20241022", max_tokens=6000, messages=[{"role": "user", "content": prompt}])
        return resp.content[0].text
    else:
        resp = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        return resp.choices[0].message.content

europass_claude = generate_europass("anthropic")
europass_openai = generate_europass("openai")

results = {
    "claude": {"europass_cv": europass_claude},
    "openai": {"europass_cv": europass_openai}
}

with open("/output/generation_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("✅ CV Europass générés")
