import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

from bibmeded.analysis.corpus import corpus_fingerprint
from bibmeded.analysis.authors import analyze_author_productivity
from bibmeded.database import get_db
from bibmeded.models import AnalysisRun, Author, Publication, SearchProject
from bibmeded.models.methodology import MethodologyStep
from bibmeded.services.export_generators import (
    generate_bibtex,
    generate_bundle,
    generate_csv,
    generate_json,
    generate_methodology,
    generate_prisma_svg,
    generate_ris,
    generate_wos_plaintext,
    slugify,
)
from bibmeded.services.screening import ScreeningDecisionLog, load_decision_log
from bibmeded.services.reporting_checklist import generate_biblio, generate_prisma_s

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


def _get_project_and_pubs(
    project_id: int, db: Session, *, with_affiliations: bool = False
) -> tuple[SearchProject, list[Publication]]:
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return project, []
    authors = joinedload(Publication.authors)
    if with_affiliations:
        authors = authors.selectinload(Author.affiliations)
    pubs = (
        db.query(Publication)
        .options(authors, joinedload(Publication.journal), joinedload(Publication.keywords))
        .filter(Publication.query_id.in_(query_ids), Publication.excluded == False)
        .order_by(Publication.year.desc())
        .all()
    )
    return project, pubs


def _get_exclusion_summary(project_id: int, db: Session) -> dict[tuple[str | None, str | None], int]:
    """Counts of records excluded in this project, keyed by (screening_stage, reason)."""
    project = db.get(SearchProject, project_id)
    if not project:
        return {}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {}
    rows = (
        db.query(Publication.screening_stage, Publication.exclusion_reason, func.count(Publication.id))
        .filter(Publication.query_id.in_(query_ids), Publication.excluded == True)
        .group_by(Publication.screening_stage, Publication.exclusion_reason)
        .all()
    )
    return {(stage, reason): count for stage, reason, count in rows}


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


def _get_decision_log(project: SearchProject, db: Session, *, with_publications: bool) -> ScreeningDecisionLog:
    return load_decision_log(
        db, project.id, [q.id for q in project.queries], with_publications=with_publications
    )


def _attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


def _biblio_for_project(project: SearchProject, steps: list[MethodologyStep],
                        exclusions: dict[tuple[str | None, str | None], int],
                        included_count: int, db: Session) -> str:
    runs = (db.query(AnalysisRun.analysis_type, AnalysisRun.parameters)
            .filter_by(project_id=project.id).order_by(AnalysisRun.analysis_type, AnalysisRun.id).all())
    return generate_biblio(
        project.name, steps, queries=project.queries, date_start=project.date_range_start,
        date_end=project.date_range_end, exclusions=exclusions, included_count=included_count,
        analyses=[(kind, (params or {}).get("bibmeded_version")) for kind, params in runs],
    )


@router.get("/checklist")
def export_checklist(project_id: int, guideline: Literal["biblio", "prisma-s"] = "biblio",
                     db: Session = Depends(get_db)):
    project, steps = _get_project_and_steps(project_id, db)
    if guideline == "prisma-s":
        content = generate_prisma_s(project.name, steps, queries=project.queries)
        extension, media_type = "txt", "text/plain"
    else:
        included_count = db.query(Publication).filter_by(project_id=project.id, excluded=False).count()
        content = _biblio_for_project(project, steps, _get_exclusion_summary(project.id, db), included_count, db)
        extension, media_type = "md", "text/markdown"
    filename = f"{slugify(project.name)}-{guideline}-{date.today().isoformat()}.{extension}"
    return StreamingResponse(iter([content]), media_type=media_type, headers=_attachment(filename))


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


@router.get("/wos")
def export_wos(project_id: int, db: Session = Depends(get_db)):
    """Web of Science tagged plain text for VOSviewer and bibliometrix."""
    project, pubs = _get_project_and_pubs(project_id, db, with_affiliations=True)
    filename = f"{slugify(project.name)}-wos-{date.today().isoformat()}.txt"
    return StreamingResponse(
        iter([generate_wos_plaintext(pubs)]),
        media_type="text/plain; charset=utf-8",
        headers=_attachment(filename),
    )


@router.get("/bibtex")
def export_bibtex(project_id: int, db: Session = Depends(get_db)):
    project, pubs = _get_project_and_pubs(project_id, db)
    filename = f"{slugify(project.name)}-{date.today().isoformat()}.bib"
    return StreamingResponse(
        iter([generate_bibtex(pubs)]),
        media_type="application/x-bibtex",
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
    exclusion_summary = _get_exclusion_summary(project_id, db)
    # Override the methodology-log "included" only when there's a real corpus to count;
    # if Publication rows haven't been ingested but methodology steps exist, fall back
    # to the log so the rendered SVG matches the methodology trace.
    query_ids = [q.id for q in project.queries]
    total_pubs = (
        db.query(Publication).filter(Publication.query_id.in_(query_ids)).count()
        if query_ids else 0
    )
    included_count: int | None = None
    if total_pubs > 0:
        included_count = (
            db.query(Publication)
            .filter(Publication.query_id.in_(query_ids), Publication.excluded == False)
            .count()
        )
    filename = f"{slugify(project.name)}-prisma-{date.today().isoformat()}.svg"
    return StreamingResponse(
        iter([generate_prisma_svg(project.name, steps, exclusion_summary, included_count=included_count)]),
        media_type="image/svg+xml",
        headers=_attachment(filename),
    )


@router.get("/methodology")
def export_methodology(project_id: int, db: Session = Depends(get_db)):
    project, steps = _get_project_and_steps(project_id, db)
    exclusion_summary = _get_exclusion_summary(project_id, db)
    fingerprint = corpus_fingerprint(db, project_id)
    author_productivity = analyze_author_productivity(db, project_id)
    if fingerprint != corpus_fingerprint(db, project_id):
        raise HTTPException(status_code=409, detail="Corpus changed during export. Please retry.")
    author_productivity["corpus_fingerprint"] = fingerprint
    decision_log = _get_decision_log(project, db, with_publications=False)
    filename = f"{slugify(project.name)}-methodology-{date.today().isoformat()}.txt"
    return StreamingResponse(
        iter([generate_methodology(project.name, steps, exclusion_summary, decision_log, author_productivity)]),
        media_type="text/plain",
        headers=_attachment(filename),
    )


@router.get("/bundle")
def export_bundle(project_id: int, db: Session = Depends(get_db)):
    """Single .zip with CSV + RIS + WoS plain text + JSON + methodology + PRISMA SVG + screening
    decision log CSV + manifest.

    Intended for journal submission: bundles everything a JOSS / systematic review reviewer
    needs to reproduce the methodology in one download.
    """
    project, pubs = _get_project_and_pubs(project_id, db, with_affiliations=True)
    _, steps = _get_project_and_steps(project_id, db)
    exclusion_summary = _get_exclusion_summary(project_id, db)
    fingerprint = corpus_fingerprint(db, project_id)
    author_productivity = analyze_author_productivity(db, project_id)
    if fingerprint != corpus_fingerprint(db, project_id):
        raise HTTPException(status_code=409, detail="Corpus changed during export. Please retry.")
    author_productivity["corpus_fingerprint"] = fingerprint
    decision_log = _get_decision_log(project, db, with_publications=True)
    filename = f"{slugify(project.name)}-bundle-{date.today().isoformat()}.zip"
    return StreamingResponse(
        iter([generate_bundle(
            project.name, pubs, steps, exclusion_summary, decision_log, author_productivity,
            biblio=_biblio_for_project(project, steps, exclusion_summary, len(pubs), db),
            prisma_s=generate_prisma_s(project.name, steps, queries=project.queries),
        )]),
        media_type="application/zip",
        headers=_attachment(filename),
    )
