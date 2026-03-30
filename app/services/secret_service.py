from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.llm import Secret


SCRAPEGRAPH_SECRET_NAME = "SGAI_API_KEY"
SCRAPEGRAPH_SECRET_TYPE = "scrapegraph"
SCRAPEGRAPH_STORAGE_BACKEND = "github_actions"


def mask_secret_value(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}{'*' * (len(cleaned) - 8)}{cleaned[-4:]}"


def build_secret_fingerprint(value: str) -> str:
    return sha256(value.strip().encode("utf-8")).hexdigest()


class SecretService:
    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory

    def upsert_scrapegraph_secret(
        self,
        db: Session,
        api_key: str,
        *,
        storage_backend: str = SCRAPEGRAPH_STORAGE_BACKEND,
        is_active: bool = True,
        source: str = "application_settings",
    ) -> Secret:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("ScrapeGraph API key cannot be empty.")

        masked_value = mask_secret_value(normalized_key)
        fingerprint = build_secret_fingerprint(normalized_key)
        now = datetime.now(timezone.utc)

        secret = db.execute(select(Secret).where(Secret.name == SCRAPEGRAPH_SECRET_NAME)).scalar_one_or_none()

        metadata = dict(secret.metadata_json or {}) if secret else {}
        metadata.update(
            {
                "provider": "scrapegraph",
                "env_var_name": SCRAPEGRAPH_SECRET_NAME,
                "fingerprint_sha256": fingerprint,
                "value_present": True,
                "managed_by": "app.services.secret_service",
                "source": source,
                "last_synced_at": now.isoformat(),
            }
        )

        if secret is None:
            secret = Secret(
                name=SCRAPEGRAPH_SECRET_NAME,
                secret_type=SCRAPEGRAPH_SECRET_TYPE,
                value_masked=masked_value,
                storage_backend=storage_backend,
                is_active=is_active,
                description="ScrapeGraph API key stored as a GitHub Actions secret reference.",
                metadata_json=metadata,
            )
            db.add(secret)
        else:
            secret.secret_type = SCRAPEGRAPH_SECRET_TYPE
            secret.value_masked = masked_value
            secret.storage_backend = storage_backend
            secret.is_active = is_active
            secret.description = "ScrapeGraph API key stored as a GitHub Actions secret reference."
            secret.metadata_json = metadata

        db.commit()
        db.refresh(secret)
        return secret

    def sync_scrapegraph_secret_from_settings(
        self,
        db: Session,
        api_key: str | None,
        *,
        storage_backend: str = SCRAPEGRAPH_STORAGE_BACKEND,
        source: str = "application_settings",
    ) -> Secret | None:
        if not api_key or not api_key.strip():
            return None
        return self.upsert_scrapegraph_secret(
            db,
            api_key,
            storage_backend=storage_backend,
            is_active=True,
            source=source,
        )


secret_service = SecretService()