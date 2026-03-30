import sys


def log(message, level="INFO", stream=None):
    output = stream if stream is not None else (sys.stderr if level in ("ERREUR", "WARN") else sys.stdout)
    print(f"[ANALYZER][{level}] {message}", file=output, flush=True)