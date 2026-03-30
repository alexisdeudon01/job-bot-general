import json
import os
from typing import Any, Dict

from generator.utils.logging import log


def file_exists(path: str) -> bool:
    return os.path.exists(path)


def read_text_file(path: str) -> str:
    log(f"Lecture du fichier texte : {path}", "INFO")
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
    log(f"Fichier texte chargé ({len(content)} caractères).", "INFO")
    return content


def read_json_file(path: str) -> Dict[str, Any]:
    log(f"Lecture du fichier JSON : {path}", "INFO")
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    log(f"Fichier JSON chargé avec succès. Clés principales : {list(data.keys())}", "INFO")
    return data


def write_json_file(path: str, payload: Dict[str, Any]) -> None:
    log(f"Écriture du fichier JSON : {path}", "INFO")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    log("Écriture JSON terminée.", "INFO")