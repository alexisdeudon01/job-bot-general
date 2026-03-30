from fastapi import FastAPI

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.pipeline import router as pipeline_router

app = FastAPI(
    title="Job Bot General Orchestrator",
    version="0.1.0",
    description="API d'orchestration FastAPI pour le pipeline analyse/génération et le dashboard.",
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(pipeline_router)