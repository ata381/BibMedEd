from collections import Counter
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject

def analyze_publication_trends(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}
    pubs = db.query(Publication.year).filter(
        Publication.query_id.in_(query_ids), Publication.year.isnot(None), Publication.excluded == False).all()
    if not pubs:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}

    yearly_counter = Counter(int(year) for (year,) in pubs if year is not None)
    yearly_items = sorted(yearly_counter.items())
    yearly_counts = [{"year": year, "count": count} for year, count in yearly_items]
    counts = [count for _, count in yearly_items]

    growth_rates = []
    for i in range(1, len(counts)):
        prev = counts[i - 1]
        rate = ((counts[i] - prev) / prev * 100) if prev > 0 else 0
        growth_rates.append({"year": yearly_items[i][0], "rate": round(rate, 1)})

    cumulative = []
    total = 0
    for year, count in yearly_items:
        total += count
        cumulative.append({"year": year, "cumulative": total})
    return {"yearly_counts": yearly_counts, "total": len(pubs), "growth_rates": growth_rates, "cumulative": cumulative}
