import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, auth, drawings, feedback, generate, generate_v2, history, render, test


class _HealthCheckFilter(logging.Filter):
    """Suppress noisy health-check access logs from probes."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/api/health" not in msg


logging.getLogger("uvicorn.access").addFilter(_HealthCheckFilter())


def create_app() -> FastAPI:
    app = FastAPI(
        title="SketchMyInfra API",
        version="2.0.0",
        docs_url="/api/docs" if settings.environment == "development" else None,
        openapi_url="/api/openapi.json" if settings.environment == "development" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(admin.router)
    app.include_router(auth.router)
    app.include_router(drawings.router)
    app.include_router(feedback.router)
    app.include_router(generate.router)
    app.include_router(generate_v2.router)
    app.include_router(history.router)
    app.include_router(render.router)

    if settings.environment == "development":
        app.include_router(test.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "2.0.0"}

    return app


app = create_app()
