from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from agent.utils.logging import log

MAX_SCRAPE_CHARS = 15000
SCRAPE_TIMEOUT_SECONDS = 30


def scrape_job(url: str) -> str:
    """Scrape raw job text from a job offer URL."""
    log(f"Scraping de l'offre d'emploi : {url}", "INFO")
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=SCRAPE_TIMEOUT_SECONDS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        log(f"Scraping terminé ({len(text)} caractères extraits).", "INFO")
        return text[:MAX_SCRAPE_CHARS]
    except Exception as error:
        log(f"Échec du scraping : {error}", "WARN")
        return f"Erreur lors du scraping de l'URL {url} : {error}"
