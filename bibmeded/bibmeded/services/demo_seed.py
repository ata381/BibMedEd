import json
import logging

from sqlalchemy.orm import Session

from bibmeded.analysis import ANALYSIS_FUNCTIONS, with_schema_version
from bibmeded.analysis.corpus import corpus_fingerprint
from bibmeded.models import AnalysisRun, SearchProject
from bibmeded.services.sample_project import get_or_create_sample_project

logger = logging.getLogger(__name__)


def seed_demo_data(db: Session) -> SearchProject:
    """Ensure the bundled sample project and all of its analyses exist.

    In read-only mode ``POST /analysis/{type}`` is rejected, so analyses are
    precomputed here; otherwise the dashboard would have nothing to show.
    """
    project, created = get_or_create_sample_project(db)
    fingerprint = corpus_fingerprint(db, project.id)
    missing = []
    for analysis_type in ANALYSIS_FUNCTIONS:
        run = (db.query(AnalysisRun).filter(AnalysisRun.project_id == project.id,
               AnalysisRun.analysis_type == analysis_type)
               .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).first())
        if not run or json.loads(run.results).get("corpus_fingerprint") != fingerprint:
            missing.append(analysis_type)
    for analysis_type in missing:
        results = with_schema_version(ANALYSIS_FUNCTIONS[analysis_type](db, project.id))
        results["corpus_fingerprint"] = fingerprint
        db.add(
            AnalysisRun(
                project_id=project.id,
                analysis_type=analysis_type,
                results=json.dumps(results),
            )
        )
    db.commit()
    logger.info(
        "demo seed: sample project id=%d %s, %d analyses precomputed",
        project.id,
        "created" if created else "already present",
        len(missing),
    )
    return project
