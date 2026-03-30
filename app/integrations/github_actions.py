import base64
from datetime import datetime
from typing import Any

import requests

from app.core.config import get_settings


GITHUB_API_BASE_URL = "https://api.github.com"


def list_github_action_runs() -> list[dict[str, Any]]:
    now = datetime.utcnow().isoformat()

    return [
        {
            "run_id": "gha-stub-001",
            "workflow_name": "docker-build",
            "status": "completed",
            "conclusion": "success",
            "branch": "main",
            "created_at": now,
            "updated_at": now,
        },
        {
            "run_id": "gha-stub-002",
            "workflow_name": "secrets-check",
            "status": "in_progress",
            "conclusion": None,
            "branch": "main",
            "created_at": now,
            "updated_at": now,
        },
    ]


def _build_github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_github_repository_and_token(
    repository: str | None = None,
    token: str | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    resolved_repository = repository or settings.github_repository
    resolved_token = token or settings.github_token

    if not resolved_repository:
        raise ValueError("GitHub repository is required to manage repository secrets.")

    if not resolved_token:
        raise ValueError("GitHub token is required to manage repository secrets.")

    return resolved_repository, resolved_token


def get_repository_public_key(
    repository: str | None = None,
    token: str | None = None,
) -> dict[str, str]:
    resolved_repository, resolved_token = _get_github_repository_and_token(repository=repository, token=token)
    response = requests.get(
        f"{GITHUB_API_BASE_URL}/repos/{resolved_repository}/actions/secrets/public-key",
        headers=_build_github_headers(resolved_token),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "key_id": payload["key_id"],
        "key": payload["key"],
    }


def build_github_secret_payload(
    secret_name: str,
    encrypted_value: str,
    key_id: str,
) -> dict[str, str]:
    return {
        "secret_name": secret_name,
        "encrypted_value": encrypted_value,
        "key_id": key_id,
    }


def seal_github_secret_value(secret_value: str, public_key: str) -> str:
    encoded_secret = base64.b64encode(secret_value.encode("utf-8")).decode("utf-8")
    encoded_key = base64.b64encode(public_key.encode("utf-8")).decode("utf-8")
    return f"UNSEALED:{encoded_key}:{encoded_secret}"


def upsert_repository_secret(
    secret_name: str,
    secret_value: str,
    repository: str | None = None,
    token: str | None = None,
    encrypted_value: str | None = None,
    key_id: str | None = None,
) -> dict[str, Any]:
    resolved_repository, resolved_token = _get_github_repository_and_token(repository=repository, token=token)

    if encrypted_value is None or key_id is None:
        public_key_payload = get_repository_public_key(repository=resolved_repository, token=resolved_token)
        key_id = public_key_payload["key_id"]
        encrypted_value = seal_github_secret_value(secret_value=secret_value, public_key=public_key_payload["key"])

    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id,
    }

    response = requests.put(
        f"{GITHUB_API_BASE_URL}/repos/{resolved_repository}/actions/secrets/{secret_name}",
        headers=_build_github_headers(resolved_token),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    return {
        "secret_name": secret_name,
        "repository": resolved_repository,
        "status_code": response.status_code,
        "updated": response.status_code in {201, 204},
    }


def ensure_scrapegraph_secret(
    secret_value: str,
    repository: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    return upsert_repository_secret(
        secret_name="SGAI_API_KEY",
        secret_value=secret_value,
        repository=repository,
        token=token,
    )