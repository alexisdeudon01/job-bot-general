from datetime import datetime
from uuid import uuid4

from app.schemas.pipeline import (
    PipelineRequest,
    PipelineRunResponse,
    PipelineRunsResponse,
    PipelineRunSummary,
    PipelineStepResult,
)


class PipelineService:
    def __init__(self) -> None:
        self._runs: list[PipelineRunSummary] = []

    def list_runs(self) -> PipelineRunsResponse:
        return PipelineRunsResponse(runs=list(reversed(self._runs)))

    def run_analyze(self, request: PipelineRequest) -> PipelineRunResponse:
        steps = [
            PipelineStepResult(
                step="collect",
                status="completed",
                detail="Payload reçu pour analyse",
                output={"source": request.source, "payload_keys": list(request.payload.keys())},
            ),
            PipelineStepResult(
                step="analyze",
                status="completed",
                detail="Analyse simulée avec succès",
                output={"score": 0.82, "highlights": ["keywords_extracted", "job_post_normalized"]},
            ),
        ]
        return self._build_run("analyze", request, steps)

    def run_generate(self, request: PipelineRequest) -> PipelineRunResponse:
        steps = [
            PipelineStepResult(
                step="prepare",
                status="completed",
                detail="Préparation du contexte de génération",
                output={"options": request.options},
            ),
            PipelineStepResult(
                step="generate",
                status="completed",
                detail="Génération simulée terminée",
                output={"artifacts": ["cv_tailored", "cover_letter_draft"]},
            ),
        ]
        return self._build_run("generate", request, steps)

    def run_full(self, request: PipelineRequest) -> PipelineRunResponse:
        steps = [
            PipelineStepResult(
                step="collect",
                status="completed",
                detail="Collecte des données d'entrée",
                output={"source": request.source},
            ),
            PipelineStepResult(
                step="analyze",
                status="completed",
                detail="Analyse simulée terminée",
                output={"match_score": 0.79},
            ),
            PipelineStepResult(
                step="generate",
                status="completed",
                detail="Génération simulée terminée",
                output={"artifacts": ["analysis_report", "application_package"]},
            ),
        ]
        return self._build_run("full", request, steps)

    def _build_run(
        self,
        pipeline_type: str,
        request: PipelineRequest,
        steps: list[PipelineStepResult],
    ) -> PipelineRunResponse:
        now = datetime.utcnow()
        run_id = f"run-{uuid4().hex[:12]}"
        response = PipelineRunResponse(
            run_id=run_id,
            pipeline_type=pipeline_type,
            status="completed",
            created_at=now,
            steps=steps,
            metadata={"source": request.source, "options": request.options},
        )
        self._runs.append(
            PipelineRunSummary(
                run_id=run_id,
                pipeline_type=pipeline_type,
                status="completed",
                created_at=now,
                updated_at=now,
                source=request.source,
            )
        )
        self._runs[:] = self._runs[-50:]
        return response


pipeline_service = PipelineService()