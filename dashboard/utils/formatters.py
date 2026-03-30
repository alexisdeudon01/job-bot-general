from __future__ import annotations

from datetime import datetime
from typing import Any


def format_number(value: Any) -> str:
    if value is None:
        return "0"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return str(value)


def format_percent(value: Any, precision: int = 0) -> str:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        numeric = 0.0
    return f"{numeric:.{precision}f} %".replace(".", ",")


def format_datetime(value: Any, fallback: str = "—") -> str:
    if value in (None, ""):
        return fallback

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    return str(value)


def format_duration_seconds(value: Any) -> str:
    try:
        total_seconds = int(float(value or 0))
    except (TypeError, ValueError):
        total_seconds = 0

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def format_status_label(value: Any) -> str:
    if value in (None, ""):
        return "unknown"
    return str(value).strip().lower().replace("_", " ")


def compact_json_preview(data: Any, limit: int = 120) -> str:
    preview = str(data)
    return preview if len(preview) <= limit else f"{preview[:limit - 3]}..."


def status_to_delta(status: Any) -> str:
    normalized = format_status_label(status)
    if normalized in {"success", "completed", "ok", "healthy", "ready"}:
        return "normal"
    if normalized in {"running", "queued", "pending", "in progress"}:
        return "off"
    return "inverse"