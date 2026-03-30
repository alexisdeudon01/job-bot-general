import sys
from typing import Optional, TextIO


def log(message: str, level: str = "INFO", stream: Optional[TextIO] = None) -> None:
    output = stream if stream is not None else (sys.stderr if level in ("ERREUR", "WARN") else sys.stdout)
    print(f"[GENERATOR][{level}] {message}", file=output, flush=True)