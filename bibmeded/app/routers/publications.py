from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Publication, SearchProject, SearchQuery
from app.schemas.publication import PublicationListResponse, PublicationResponse

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
    for pub in publications:
        item = PublicationResponse(id=pub.id, pmid=pub.pmid, doi=pub.doi, title=pub.title, abstract=pub.abstract,
            year=pub.year, publication_type=pub.publication_type, citation_count=pub.citation_count,
            excluded=pub.excluded,
            journal_name=pub.journal.name if pub.journal else None,
            authors=[{"id": a.id, "name": a.name, "orcid": a.orcid} for a in pub.authors])
        items.append(item)
    return PublicationListResponse(total=total, excluded_count=excluded_count, items=items)

@router.post("/bulk-exclude")
def bulk_exclude(project_id: int, body: dict, db: Session = Depends(get_db)):
    """Exclude all publications with citation_count below threshold."""
    threshold = body.get("citation_threshold", 0)
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"excluded_count": 0}
    updated = (
        db.query(Publication)
        .filter(
            Publication.query_id.in_(query_ids),
            Publication.excluded == False,
            (Publication.citation_count == None) | (Publication.citation_count <= threshold),
        )
        .update({Publication.excluded: True}, synchronize_session="fetch")
    )
    db.commit()
    return {"excluded_count": updated}

@router.patch("/{publication_id}/exclude")
def toggle_exclude(project_id: int, publication_id: int, db: Session = Depends(get_db)):
    pub = db.get(Publication, publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    pub.excluded = not pub.excluded
    db.commit()
    return {"id": pub.id, "excluded": pub.excluded}
