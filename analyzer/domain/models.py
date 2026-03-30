from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NLPResult:
    clean_text: str
    entities: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean_text": self.clean_text,
            "entities": self.entities,
            "keywords": self.keywords,
        }


@dataclass
class AnalyzerArtifacts:
    job_url: str
    cv_text: str
    raw_job_text: str
    nlp_result: NLPResult
    cv_analysis: Dict[str, Any]
    job_json: Dict[str, Any]
    fallback_reason: Optional[str] = None