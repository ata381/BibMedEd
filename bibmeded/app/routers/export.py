from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Publication, SearchProject
from app.models.methodology import MethodologyStep
from app.services.export_generators import (
    generate_bundle,
    generate_csv,
    generate_json,
    generate_methodology,
    generate_prisma_svg,
    generate_ris,
    slugify,
)

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


def _get_project_and_pubs(project_id: int, db: Session) -> tuple[SearchProject, list[Publication]]:
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return project, []
    pubs = (
        db.query(Publication)
        .options(joinedload(Publication.authors), joinedload(Publication.journal), joinedload(Publication.keywords))
        .filter(Publication.query_id.in_(query_ids), Publication.excluded == False)
        .order_by(Publication.year.desc())
        .all()
    )
    return project, pubs


def _get_project_and_steps(project_id: int, db: Session) -> tuple[SearchProject, list[MethodologyStep]]:
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return project, []
    steps = (
        db.query(MethodologyStep)
        .filter(MethodologyStep.query_id.in_(query_ids))
        .order_by(MethodologyStep.query_id, MethodologyStep.step_order)
        .all()
    )
    return project, steps


def _attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/csv")
def export_csv(project_id: int, db: Session = Depends(get_db)):
    project, pubs = _get_project_and_pubs(project_id, db)
    filename = f"{slugify(project.name)}-{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([generate_csv(pubs)]),
        media_type="text/csv",
        headers=_attachment(filename),
    )


@router.get("/ris")
def export_ris(project_id: int, db: Session = Depends(get_db)):
    project, pubs = _get_project_and_pubs(project_id, db)
    filename = f"{slugify(project.name)}-{date.today().isoformat()}.ris"
    return StreamingResponse(
        iter([generate_ris(pubs)]),
        media_type="application/x-research-info-systems",
        headers=_attachment(filename),
    )


@router.get("/json")
def export_json(project_id: int, db: Session = Depends(get_db)):
    """Versioned JSON export for programmatic / notebook consumers."""
    project, pubs = _get_project_and_pubs(project_id, db)
    filename = f"{slugify(project.name)}-{date.today().isoformat()}.json"
    return StreamingResponse(
        iter([generate_json(project.name, pubs)]),
        media_type="application/json",
        headers=_attachment(filename),
    )


@router.get("/prisma")
def export_prisma(project_id: int, db: Session = Depends(get_db)):
    project, steps = _get_project_and_steps(project_id, db)
    filename = f"{slugify(project.name)}-prisma-{date.today().isoformat()}.svg"
    return StreamingResponse(
        iter([generate_prisma_svg(project.name, steps)]),
        media_type="image/svg+xml",
        headers=_attachment(filename),
    )


@router.get("/methodology")
def export_methodology(project_id: int, db: Session = Depends(get_db)):
    project, steps = _get_project_and_steps(project_id, db)
    filename = f"{slugify(project.name)}-methodology-{date.today().isoformat()}.txt"
    return StreamingResponse(
        iter([generate_methodology(project.name, steps)]),
        media_type="text/plain",
        headers=_attachment(filename),
    )


@router.get("/bundle")
def export_bundle(project_id: int, db: Session = Depends(get_db)):
    """Single .zip with CSV + RIS + methodology + PRISMA SVG + manifest.

    Intended for journal submission: bundles everything a JOSS / systematic review reviewer
    needs to reproduce the methodology in one download.
    """
    project, pubs = _get_project_and_pubs(project_id, db)
    _, steps = _get_project_and_steps(project_id, db)
    filename = f"{slugify(project.name)}-bundle-{date.today().isoformat()}.zip"
    return StreamingResponse(
        iter([generate_bundle(project.name, pubs, steps)]),
        media_type="application/zip",
        headers=_attachment(filename),
    )
