from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class GenerationPaths:
    job_data_path: str = "/output/job_data.json"
    resume_path: str = "/data/resume_europass.txt"
    results_path: str = "/output/generation_results.json"


@dataclass
class ProviderResult:
    provider: str
    status: str
    model: Optional[str] = None
    europass_cv: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "provider": self.provider,
            "status": self.status,
            "model": self.model,
        }
        if self.europass_cv is not None:
            payload["europass_cv"] = self.europass_cv
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass
class GenerationContext:
    job_data: Dict[str, Any]
    original_cv: str
    prompt: str
    openai_model: Optional[str] = None
    results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
