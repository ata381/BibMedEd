import csv
import io
import re
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Publication, SearchProject
from app.models.methodology import MethodologyStep
from app.models import SearchQuery

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    return re.sub(r"[\s_]+", "-", slug)[:50]


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


@router.get("/csv")
def export_csv(project_id: int, db: Session = Depends(get_db)):
    project, pubs = _get_project_and_pubs(project_id, db)
    filename = f"{_slugify(project.name)}-{date.today().isoformat()}.csv"
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["PMID", "DOI", "Title", "Authors", "Journal", "Year", "Citations", "Keywords", "Abstract"])
    for pub in pubs:
        writer.writerow([
            pub.pmid,
            pub.doi or "",
            pub.title,
            "; ".join(a.name for a in pub.authors),
            pub.journal.name if pub.journal else "",
            pub.year or "",
            pub.citation_count or 0,
            "; ".join(k.term for k in pub.keywords),
            (pub.abstract or "").replace("\n", " "),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ris")
def export_ris(project_id: int, db: Session = Depends(get_db)):
    project, pubs = _get_project_and_pubs(project_id, db)
    filename = f"{_slugify(project.name)}-{date.today().isoformat()}.ris"
    lines: list[str] = []
    for pub in pubs:
        lines.append("TY  - JOUR")
        lines.append(f"TI  - {pub.title}")
        for author in pub.authors:
            lines.append(f"AU  - {author.name}")
        if pub.journal:
            lines.append(f"JO  - {pub.journal.name}")
        if pub.year:
            lines.append(f"PY  - {pub.year}")
        if pub.doi:
            lines.append(f"DO  - {pub.doi}")
        lines.append(f"AN  - {pub.pmid}")
        if pub.abstract:
            lines.append(f"AB  - {pub.abstract.replace(chr(10), ' ')}")
        for kw in pub.keywords:
            lines.append(f"KW  - {kw.term}")
        lines.append("ER  - ")
        lines.append("")
    content = "\n".join(lines)
    return StreamingResponse(
        iter([content]),
        media_type="application/x-research-info-systems",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/methodology")
def export_methodology(project_id: int, db: Session = Depends(get_db)):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query_ids = [q.id for q in project.queries]
    steps = []
    if query_ids:
        steps = (
            db.query(MethodologyStep)
            .filter(MethodologyStep.query_id.in_(query_ids))
            .order_by(MethodologyStep.query_id, MethodologyStep.step_order)
            .all()
        )

    lines = [
        f'METHODOLOGY LOG — Project: "{project.name}"',
        f"Generated: {date.today().isoformat()}",
        "Tool: BibMedEd (https://github.com/ata381/bibmeded)",
        "",
    ]

    if not steps:
        lines.append("No methodology steps recorded for this project.")
    else:
        phase_labels = {
            "search": "SEARCH STRATEGY",
            "fetch": "DATA COLLECTION",
            "dedup": "DEDUPLICATION",
            "enrichment": "ENRICHMENT",
            "exclusion": "EXCLUSION",
        }
        current_phase = None
        for step in steps:
            phase_header = phase_labels.get(step.phase, step.phase.upper())
            if phase_header != current_phase:
                current_phase = phase_header
                lines.append(current_phase)
            lines.append(f"  Step {step.step_order}: {step.action}")
            if step.phase == "search":
                query_str = step.parameters.get("query", "")
                if query_str:
                    lines.append(f"    Query: {query_str}")
                lines.append(f"    Results: {step.records_out} records")
            elif step.phase == "fetch":
                lines.append(f"    Retrieved: {step.records_out} of {step.records_in} ({step.records_affected} unavailable)")
            elif step.phase == "dedup":
                method = step.parameters.get("method", "unknown")
                fields = step.parameters.get("fields", step.parameters.get("field", ""))
                lines.append(f"    Method: {method} on {fields}")
                lines.append(f"    Removed: {step.records_affected} duplicates ({step.records_in} → {step.records_out})")
            elif step.phase == "enrichment":
                source_name = step.parameters.get("source", "")
                enriched = step.parameters.get("enriched", 0)
                missing = step.parameters.get("missing", 0)
                lines.append(f"    Source: {source_name}")
                lines.append(f"    Enriched: {enriched} of {step.records_in} records ({missing} not found)")
            elif step.phase == "exclusion":
                lines.append(f"    Excluded: {step.records_affected} records ({step.records_in} → {step.records_out})")
            lines.append("")

        last_step = steps[-1]
        lines.append("FINAL DATASET")
        lines.append(f"  Studies included: {last_step.records_out}")
        lines.append("")

    content = "\n".join(lines)
    filename = f"{_slugify(project.name)}-methodology-{date.today().isoformat()}.txt"
    return StreamingResponse(
        iter([content]),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
