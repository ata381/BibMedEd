from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import QueryStatus, SearchProject, SearchQuery
from app.schemas.search import SearchRequest, SearchStatusResponse
from app.workers.tasks import run_search

router = APIRouter(prefix="/api/projects/{project_id}/search", tags=["search"])

STALE_THRESHOLD_MINUTES = 15

@router.post("", status_code=202, response_model=SearchStatusResponse)
def trigger_search(project_id: int, body: SearchRequest, db: Session = Depends(get_db)):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query = SearchQuery(project_id=project_id, query_string=body.query_string, database=body.source)
    db.add(query)
    db.commit()
    db.refresh(query)
    run_search.delay(query.id, body.source)
    return SearchStatusResponse(query_id=query.id, status=query.status.value, result_count=None)

@router.get("/latest", response_model=SearchStatusResponse)
def get_latest_search(project_id: int, db: Session = Depends(get_db)):
    query = db.query(SearchQuery).filter(
        SearchQuery.project_id == project_id
    ).order_by(SearchQuery.id.desc()).first()
    if not query:
        raise HTTPException(status_code=404, detail="No searches found for this project")
    return SearchStatusResponse(
        query_id=query.id,
        status=query.status.value,
        result_count=query.result_count,
        raw_result_count=query.raw_result_count,
        duplicate_count=query.duplicate_count,
    )

@router.get("/{query_id}", response_model=SearchStatusResponse)
def get_search_status(project_id: int, query_id: int, db: Session = Depends(get_db)):
    query = db.get(SearchQuery, query_id)
    if not query or query.project_id != project_id:
        raise HTTPException(status_code=404, detail="Search query not found")
    # Auto-fail stale running queries (zombie task protection)
    if query.status == QueryStatus.running:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_THRESHOLD_MINUTES)
        created = query.project.created_at  # proxy for query start
        if query.executed_at:
            pass  # already has a timestamp, not stale
        elif created.replace(tzinfo=timezone.utc) < cutoff:
            query.status = QueryStatus.failed
            db.commit()
    return SearchStatusResponse(
        query_id=query.id,
        status=query.status.value,
        result_count=query.result_count,
        raw_result_count=query.raw_result_count,
        duplicate_count=query.duplicate_count,
    )
