import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import projects, search, publications, analysis, export

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="BibMedEd",
        description="Bibliometric Analysis Platform for Medical Education",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "type": type(exc).__name__,
            },
        )

    app.include_router(projects.router)
    app.include_router(search.router)
    app.include_router(publications.router)
    app.include_router(analysis.router)
    app.include_router(export.router)

    @app.get("/api/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()
