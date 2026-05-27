import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SearchProject, AnalysisRun
from app.analysis import ANALYSIS_FUNCTIONS, ANALYSIS_SCHEMA_VERSION
from app.schemas.analysis import AnalysisResponse

router = APIRouter(prefix="/api/projects/{project_id}/analysis", tags=["analysis"])


def _with_schema_version(results: dict) -> dict:
    """Stamp every analysis response with the schema version so programmatic users can
    pin against a known shape."""
    if isinstance(results, dict) and "schema_version" not in results:
        return {"schema_version": ANALYSIS_SCHEMA_VERSION, **results}
    return results


@router.post("/{analysis_type}", response_model=AnalysisResponse)
def run_analysis(project_id: int, analysis_type: str, db: Session = Depends(get_db)):
    if analysis_type not in ANALYSIS_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown analysis type: {analysis_type}")
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    func = ANALYSIS_FUNCTIONS[analysis_type]
    results = _with_schema_version(func(db, project_id))
    run = AnalysisRun(project_id=project_id, analysis_type=analysis_type, results=json.dumps(results))
    db.add(run)
    db.commit()
    db.refresh(run)
    return AnalysisResponse(id=run.id, project_id=run.project_id, analysis_type=run.analysis_type, results=results, created_at=run.created_at)

@router.get("/{analysis_type}", response_model=AnalysisResponse)
def get_analysis(project_id: int, analysis_type: str, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(AnalysisRun.project_id == project_id, AnalysisRun.analysis_type == analysis_type).order_by(AnalysisRun.created_at.desc()).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found. Run it first.")
    return AnalysisResponse(id=run.id, project_id=run.project_id, analysis_type=run.analysis_type, results=_with_schema_version(json.loads(run.results)), created_at=run.created_at)
