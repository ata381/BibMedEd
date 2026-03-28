import csv
import io
import re
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Publication, SearchProject

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
