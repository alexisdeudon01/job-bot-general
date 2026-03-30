from fastapi import APIRouter

from app.schemas.pipeline import PipelineRequest, PipelineRunResponse, PipelineRunsResponse
from app.services.pipeline_service import pipeline_service

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.post("/analyze", response_model=PipelineRunResponse)
def analyze_pipeline(request: PipelineRequest) -> PipelineRunResponse:
    return pipeline_service.run_analyze(request)


@router.post("/generate", response_model=PipelineRunResponse)
def generate_pipeline(request: PipelineRequest) -> PipelineRunResponse:
    return pipeline_service.run_generate(request)


@router.post("/full", response_model=PipelineRunResponse)
def run_full_pipeline(request: PipelineRequest) -> PipelineRunResponse:
    return pipeline_service.run_full(request)


@router.get("/runs", response_model=PipelineRunsResponse)
def list_pipeline_runs() -> PipelineRunsResponse:
    return pipeline_service.list_runs()