from datetime import datetime
from typing import Any


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