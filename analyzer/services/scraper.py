import requests
from bs4 import BeautifulSoup

from analyzer.utils.logging import log


def scrape_job_offer(url: str, max_chars: int = 30000) -> str:
    log(f"Démarrage du scraping de l'offre depuis l'URL : {url}", "INFO")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=20)
    log(f"Réponse HTTP reçue avec le statut {response.status_code}", "INFO")
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()

    extracted_text = soup.get_text(separator="\n", strip=True)[:max_chars]
    log(f"Scraping terminé, {len(extracted_text)} caractères de texte exploitable extraits.", "INFO")
    return extracted_text