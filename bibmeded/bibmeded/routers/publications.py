import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from bibmeded.database import get_db
from bibmeded.models import Publication, SearchProject
from bibmeded.schemas.publication import (
    BulkExcludeRequest,
    BulkExcludeResponse,
    PublicationListResponse,
    PublicationResponse,
    ToggleExcludeRequest,
    ToggleExcludeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/publications", tags=["publications"])

@router.get("", response_model=PublicationListResponse)
def list_publications(project_id: int, sort_by: str = Query("year", enum=["year", "title", "citation_count"]),
    order: str = Query("desc", enum=["asc", "desc"]), limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return PublicationListResponse(total=0, items=[])
    base_query = db.query(Publication).options(joinedload(Publication.authors), joinedload(Publication.journal)).filter(Publication.query_id.in_(query_ids))
    total = base_query.count()
    excluded_count = base_query.filter(Publication.excluded == True).count()
    sort_col = getattr(Publication, sort_by, Publication.year)
    if order == "desc":
        sort_col = sort_col.desc()
    else:
        sort_col = sort_col.asc()
    publications = base_query.order_by(sort_col).offset(offset).limit(limit).all()
    items = []
    skipped = 0
    for pub in publications:
        try:
            item = PublicationResponse(
                id=pub.id, pmid=pub.pmid or "", doi=pub.doi, title=pub.title or "Untitled",
                abstract=pub.abstract, year=pub.year, publication_type=pub.publication_type,
                citation_count=pub.citation_count, excluded=pub.excluded,
                exclusion_reason=pub.exclusion_reason, screening_stage=pub.screening_stage,
                journal_name=pub.journal.name if pub.journal else None,
                authors=[{"id": a.id, "name": a.name, "orcid": a.orcid} for a in pub.authors],
            )
            items.append(item)
        except Exception as exc:
            skipped += 1
            logger.warning("Skipping malformed publication id=%s: %s", pub.id, exc, exc_info=True)
    if skipped:
        logger.info("list_publications: %d malformed publications skipped out of %d returned", skipped, len(publications))
    return PublicationListResponse(total=total, excluded_count=excluded_count, items=items)


@router.post("/bulk-exclude", response_model=BulkExcludeResponse)
def bulk_exclude(project_id: int, body: BulkExcludeRequest, db: Session = Depends(get_db)):
    """Exclude all publications with citation_count at or below the threshold; stamps
    every affected row with the supplied PRISMA exclusion reason and screening stage
    (default ``title_abstract``)."""
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return BulkExcludeResponse(excluded_count=0, reason=body.reason, screening_stage=body.screening_stage)
    updated = (
        db.query(Publication)
        .filter(
            Publication.query_id.in_(query_ids),
            Publication.excluded == False,
            (Publication.citation_count == None) | (Publication.citation_count <= body.citation_threshold),
        )
        .update(
            {
                Publication.excluded: True,
                Publication.exclusion_reason: body.reason,
                Publication.screening_stage: body.screening_stage,
            },
            synchronize_session="fetch",
        )
    )
    db.commit()
    return BulkExcludeResponse(excluded_count=updated, reason=body.reason, screening_stage=body.screening_stage)


@router.patch("/{publication_id}/exclude", response_model=ToggleExcludeResponse)
def toggle_exclude(
    project_id: int,
    publication_id: int,
    body: ToggleExcludeRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    """Toggle a publication between included and excluded. Excluding records the
    PRISMA reason (default ``other``) and screening stage (default
    ``title_abstract``); re-including clears both."""
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pub = db.get(Publication, publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    project_query_ids = {q.id for q in project.queries}
    if pub.query_id not in project_query_ids:
        raise HTTPException(status_code=404, detail="Publication not found")
    body = body or ToggleExcludeRequest()
    pub.excluded = not pub.excluded
    if pub.excluded:
        pub.exclusion_reason = body.reason or "other"
        pub.screening_stage = body.screening_stage
    else:
        pub.exclusion_reason = None
        pub.screening_stage = None
    db.commit()
    return ToggleExcludeResponse(
        id=pub.id,
        excluded=pub.excluded,
        exclusion_reason=pub.exclusion_reason,
        screening_stage=pub.screening_stage,
    )
