from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import projects, search, publications, analysis


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

    app.include_router(projects.router)
    app.include_router(search.router)
    app.include_router(publications.router)
    app.include_router(analysis.router)

    @app.get("/api/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()
