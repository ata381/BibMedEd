"""Save read-only sample API responses for the GitHub Pages frontend."""

import os
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def build_demo(destination: Path) -> None:
    with TemporaryDirectory() as directory:
        # Set these before importing the application. The deployment build can
        # only read records seeded into a fresh, disposable SQLite database.
        os.environ["BIBMEDED_DATABASE_URL"] = f"sqlite:///{(Path(directory) / 'demo.db').as_posix()}"
        os.environ["BIBMEDED_READ_ONLY"] = "true"

        from bibmeded.analysis import ANALYSIS_FUNCTIONS
        from bibmeded.database import Base, get_engine, get_read_only_engine
        from bibmeded.main import app

        Base.metadata.create_all(get_engine())
        try:
            with TestClient(app) as client:
                write_snapshot(client, destination, ANALYSIS_FUNCTIONS)
        finally:
            get_read_only_engine().dispose()
            get_engine().dispose()


def write_snapshot(client: TestClient, destination: Path, analysis_types: Iterable[str]) -> None:
    project_path = "/api/projects/1"
    routes = {
        "/api/config": "api/config.json",
        "/api/adapters": "api/adapters.json",
        "/api/projects": "api/projects.json",
        project_path: "api/projects/1.json",
        f"{project_path}/search/latest": "api/projects/1/search/latest.json",
        f"{project_path}/publications?sort_by=citation_count&order=desc&limit=20&offset=0":
            "api/projects/1/publications.json",
    }
    routes.update({
        f"{project_path}/analysis/{kind}": f"api/projects/1/analysis/{kind}.json"
        for kind in analysis_types
    })
    reports = {
        "csv": "sample.csv",
        "ris": "sample.ris",
        "wos": "sample-wos.txt",
        "bibtex": "sample.bib",
        "json": "sample.json",
        "methodology": "sample-methodology.txt",
        "prisma": "sample-prisma.svg",
        "checklist?guideline=biblio": "sample-biblio.md",
        "checklist?guideline=prisma-s": "sample-prisma-s.txt",
        "bundle": "sample-bundle.zip",
    }
    routes.update({
        f"{project_path}/export/{route}": f"api/projects/1/export/{filename}"
        for route, filename in reports.items()
    })

    for route, filename in routes.items():
        response = client.get(route)
        response.raise_for_status()
        if route == "/api/projects":
            projects = response.json()
            if len(projects) != 1 or projects[0]["id"] != 1:
                raise RuntimeError("The static demo needs exactly one seeded project with ID 1.")
        if filename == "api/projects/1/publications.json":
            publications = response.json()
            if len(publications["items"]) != publications["total"]:
                raise RuntimeError("The synthetic project needs pagination support before it can be published.")
        output = destination / filename
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)


if __name__ == "__main__":
    build_demo(Path(__file__).resolve().parents[1] / "frontend" / "public" / "demo-data")
