from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SearchProject, SearchQuery
from app.schemas.search import SearchRequest, SearchStatusResponse
from app.workers.tasks import run_pubmed_search

router = APIRouter(prefix="/api/projects/{project_id}/search", tags=["search"])

@router.post("", status_code=202, response_model=SearchStatusResponse)
def trigger_search(project_id: int, body: SearchRequest, db: Session = Depends(get_db)):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query = SearchQuery(project_id=project_id, query_string=body.query_string, database=body.database)
    db.add(query)
    db.commit()
    db.refresh(query)
    run_pubmed_search.delay(query.id)
    return SearchStatusResponse(query_id=query.id, status=query.status.value, result_count=None)

@router.get("/{query_id}", response_model=SearchStatusResponse)
def get_search_status(project_id: int, query_id: int, db: Session = Depends(get_db)):
    query = db.get(SearchQuery, query_id)
    if not query or query.project_id != project_id:
        raise HTTPException(status_code=404, detail="Search query not found")
    return SearchStatusResponse(query_id=query.id, status=query.status.value, result_count=query.result_count)
