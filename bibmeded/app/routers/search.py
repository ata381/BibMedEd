import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import QueryStatus, SearchProject, SearchQuery
from app.schemas.search import SearchRequest, SearchStatusResponse
from app.workers.tasks import run_search

router = APIRouter(prefix="/api/projects/{project_id}/search", tags=["search"])


def _infer_progress(query: SearchQuery) -> float | None:
    if query.status == QueryStatus.completed:
        return 100.0
    if query.status == QueryStatus.failed:
        return 0.0
    return None

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
    # Lazy import: app.main isn't fully initialized yet when this module is first
    # imported (app.main imports app.routers.search while defining request_id_ctx),
    # so importing at call time avoids a circular-import failure.
    from app.main import request_id_ctx
    request_id = request_id_ctx.get()
    run_search.delay(query.id, body.source, body.year_start, body.year_end, body.max_results, request_id)
    logger.info(
        "search dispatched project_id=%d query_id=%d source=%s max_results=%d request_id=%s",
        project_id, query.id, body.source, body.max_results, request_id,
    )
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
        progress=_infer_progress(query),
    )


@router.get("/{query_id}", response_model=SearchStatusResponse)
def get_search_status(project_id: int, query_id: int, db: Session = Depends(get_db)):
    query = db.get(SearchQuery, query_id)
    if not query or query.project_id != project_id:
        raise HTTPException(status_code=404, detail="Search query not found")
    if query.status == QueryStatus.running:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_THRESHOLD_MINUTES)
        started = query.created_at
        if started and started.replace(tzinfo=timezone.utc) < cutoff:
            query.status = QueryStatus.failed
            db.commit()
    return SearchStatusResponse(
        query_id=query.id,
        status=query.status.value,
        result_count=query.result_count,
        raw_result_count=query.raw_result_count,
        duplicate_count=query.duplicate_count,
        progress=_infer_progress(query),
    )
