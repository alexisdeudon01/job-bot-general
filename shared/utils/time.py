from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    return utc_now().replace(tzinfo=None)


def to_isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()