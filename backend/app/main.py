from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import render


def create_app() -> FastAPI:
    app = FastAPI(
        title="SketchMyInfra API",
        version="2.0.0",
        docs_url="/api/docs" if settings.environment == "development" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(render.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "2.0.0"}

    return app


app = create_app()
