import pandas as pd
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject

def analyze_publication_trends(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}
    pubs = db.query(Publication.year, Publication.id).filter(
        Publication.query_id.in_(query_ids), Publication.year.isnot(None), Publication.excluded == False).all()
    if not pubs:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}
    df = pd.DataFrame(pubs, columns=["year", "id"])
    yearly = df.groupby("year").size().reset_index(name="count").sort_values("year")
    yearly_counts = [{"year": int(r["year"]), "count": int(r["count"])} for _, r in yearly.iterrows()]
    counts = yearly["count"].tolist()
    growth_rates = []
    for i in range(1, len(counts)):
        prev = counts[i - 1]
        rate = ((counts[i] - prev) / prev * 100) if prev > 0 else 0
        growth_rates.append({"year": int(yearly.iloc[i]["year"]), "rate": round(rate, 1)})
    cumulative = []
    total = 0
    for _, r in yearly.iterrows():
        total += int(r["count"])
        cumulative.append({"year": int(r["year"]), "cumulative": total})
    return {"yearly_counts": yearly_counts, "total": len(pubs), "growth_rates": growth_rates, "cumulative": cumulative}
