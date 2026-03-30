from datetime import datetime

from app.schemas.dashboard import ServiceStatus


def get_provider_statuses() -> list[ServiceStatus]:
    timestamp = datetime.utcnow().isoformat()

    return [
        ServiceStatus(
            name="postgresql",
            status="unknown",
            detail="Intégration base de données à brancher",
            metadata={"checked_at": timestamp},
        ),
        ServiceStatus(
            name="redis",
            status="unknown",
            detail="Intégration cache/queue à brancher",
            metadata={"checked_at": timestamp},
        ),
        ServiceStatus(
            name="llm-provider",
            status="stub",
            detail="Provider IA non configuré pour le moment",
            metadata={"checked_at": timestamp},
        ),
    ]