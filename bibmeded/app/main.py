import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import projects, search, publications, analysis, export, adapters

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="BibMedEd",
        description=(
            "Bibliometric Analysis Platform for Medical Education.\n\n"
            "**Programmatic access**: this is the auto-generated OpenAPI surface. "
            "Interactive Swagger UI lives at [`/docs`](/docs), ReDoc at [`/redoc`](/redoc), "
            "and the raw spec at [`/openapi.json`](/openapi.json) for client codegen. "
            "Analysis responses are stamped with a `schema_version` field so downstream "
            "pipelines can pin against a known shape. See "
            "[`docs/scripting.md`](https://github.com/ata381/BibMedEd/blob/master/docs/scripting.md) "
            "for an end-to-end Jupyter-notebook example."
        ),
        version="0.2.0",
        contact={"name": "BibMedEd", "url": "https://github.com/ata381/BibMedEd"},
        license_info={"name": "MIT", "url": "https://github.com/ata381/BibMedEd/blob/master/LICENSE"},
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
            },
        )

    app.include_router(projects.router)
    app.include_router(search.router)
    app.include_router(publications.router)
    app.include_router(analysis.router)
    app.include_router(export.router)
    app.include_router(adapters.router)

    @app.get("/api/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()
