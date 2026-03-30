from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentPaths:
    resume_path: str = "/data/resume_europass.txt"
    result_path: str = "/output/agent_result.json"


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: Dict[str, Any]
    result: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
        }


@dataclass
class AgentResult:
    job_url: str
    recommendation: str  # "apply" | "skip" | "unclear"
    fit_score: Optional[int] = None
    reasoning: Optional[str] = None
    cover_letter: Optional[str] = None
    adapted_cv: Optional[str] = None
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_url": self.job_url,
            "recommendation": self.recommendation,
            "fit_score": self.fit_score,
            "reasoning": self.reasoning,
            "cover_letter": self.cover_letter,
            "adapted_cv": self.adapted_cv,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "provider": self.provider,
            "model": self.model,
            "error": self.error,
        }
