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
                detail="Analyse préparatoire terminée",
                output={"mode": "mcp_first"},
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
                output={"artifacts": ["cover_letter_draft", "fit_assessment_json"]},
            ),
        ]
        return self._build_run("generate", request, steps)

    def run_full(self, request: PipelineRequest) -> PipelineRunResponse:
        payload = dict(request.payload)
        job_url = (
            payload.get("job_url")
            or request.job_url
            or ""
        )
        cv_pdf_path = (
            payload.get("cv_pdf_path")
            or request.cv_pdf_path
            or "data/cv.pdf"
        )

        entities = [
            {"name": "Python", "type": "skill"},
            {"name": "FastAPI", "type": "skill"},
            {"name": "OpenAI", "type": "provider"},
            {"name": "Anthropic", "type": "provider"},
        ]

        steps = [
            PipelineStepResult(
                step="1_test_ai_connectivity_via_mcp",
                status="completed",
                detail="Connexion MCP testée pour OpenAI et Anthropic.",
                output={"openai": "ok", "anthropic": "ok", "tool": "mcp.providers_connectivity"},
            ),
            PipelineStepResult(
                step="2_convert_cv_pdf_to_json",
                status="completed",
                detail="Conversion CV PDF -> JSON via MCP.",
                output={"tool": "mcp.europass_pdf_to_structured_json", "cv_pdf_path": cv_pdf_path},
            ),
            PipelineStepResult(
                step="3_download_job_html",
                status="completed",
                detail="Téléchargement HTML de l'offre via MCP.",
                output={"tool": "mcp.job_url_to_html", "job_url": job_url},
            ),
            PipelineStepResult(
                step="4_clean_job_html_noise",
                status="completed",
                detail="Nettoyage du bruit HTML (balises/scripts/styles).",
                output={"tool": "mcp.clean_html_content", "cleaning": ["remove_html_tags", "normalize_spaces"]},
            ),
            PipelineStepResult(
                step="5_convert_job_to_json",
                status="completed",
                detail="Conversion job nettoyé -> JSON structuré.",
                output={"tool": "mcp.job_text_to_json", "schema": "job_description_json"},
            ),
            PipelineStepResult(
                step="6_extract_entities_from_job_json",
                status="completed",
                detail="Extraction des entités depuis le JSON job.",
                output={"tool": "mcp.extract_entities", "entities_count": len(entities), "entities": entities},
            ),
            PipelineStepResult(
                step="7_upsert_entities_in_db",
                status="completed",
                detail="Vérification/ajout des entités dans la DB.",
                output={"tool": "mcp.upsert_entities", "upserted": len(entities), "known": 0, "created": len(entities)},
            ),
            PipelineStepResult(
                step="8_osint_for_each_entity",
                status="completed",
                detail="OSINT sur chaque entité et stockage DB.",
                output={"tool": "mcp.osint_entities", "processed_entities": len(entities), "db_write": "ok"},
            ),
            PipelineStepResult(
                step="9_generate_master_prompt_from_json_inputs",
                status="completed",
                detail="Prompt généré via MCP à partir de cv_json + job_json + entités JSON.",
                output={
                    "tool": "mcp.generate_master_prompt",
                    "outputs": ["strengths_weaknesses", "cover_letter", "success_probability"],
                },
            ),
            PipelineStepResult(
                step="10_send_prompt_to_openai_and_store",
                status="completed",
                detail="Prompt envoyé à OpenAI avec attachments JSON puis stockage DB.",
                output={"tool": "mcp.career_strategy_openai", "db_write": "ok"},
            ),
            PipelineStepResult(
                step="11_send_prompt_to_anthropic_and_store",
                status="completed",
                detail="Prompt envoyé à Anthropic avec attachments JSON puis stockage DB.",
                output={"tool": "mcp.career_strategy_anthropic", "db_write": "ok"},
            ),
            PipelineStepResult(
                step="12_generate_complete_pdf_report",
                status="completed",
                detail="Rapport PDF final généré via MCP.",
                output={"tool": "mcp.generate_final_report_pdf", "report_path": "output/final_report.pdf"},
            ),
        ]

        return self._build_run(
            "full",
            request,
            steps,
            metadata={
                "source": request.source,
                "options": request.options,
                "job_url": job_url,
                "cv_pdf_path": cv_pdf_path,
                "mode": "mcp_first_stubbed_orchestrator",
            },
        )

    def _build_run(
        self,
        pipeline_type: str,
        request: PipelineRequest,
        steps: list[PipelineStepResult],
        metadata: dict | None = None,
    ) -> PipelineRunResponse:
        now = datetime.utcnow()
        run_id = f"run-{uuid4().hex[:12]}"
        final_status = "completed" if all(step.status == "completed" for step in steps) else "failed"
        response = PipelineRunResponse(
            run_id=run_id,
            pipeline_type=pipeline_type,
            status=final_status,
            created_at=now,
            steps=steps,
            metadata=metadata or {"source": request.source, "options": request.options},
        )
        self._runs.append(
            PipelineRunSummary(
                run_id=run_id,
                pipeline_type=pipeline_type,
                status=final_status,
                created_at=now,
                updated_at=now,
                source=request.source,
            )
        )
        self._runs[:] = self._runs[-50:]
        return response


pipeline_service = PipelineService()
