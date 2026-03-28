from collections import Counter
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject

def analyze_journals(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return {"top_journals": [], "bradford_zones": [], "total_journals": 0}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"top_journals": [], "bradford_zones": [], "total_journals": 0}
    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids), Publication.excluded == False).all()
    journal_counter = Counter()
    journal_citations = Counter()
    for pub in pubs:
        if pub.journal:
            journal_counter[pub.journal.name] += 1
            journal_citations[pub.journal.name] += pub.citation_count or 0
    top_journals = [
        {"name": j, "pub_count": n, "avg_citations": round(journal_citations[j] / n, 1) if n > 0 else 0}
        for j, n in journal_counter.most_common(20)]
    sorted_journals = journal_counter.most_common()
    total_pubs = sum(n for _, n in sorted_journals)
    third = total_pubs / 3 if total_pubs > 0 else 1
    zones = []
    cumulative = 0
    zone_num = 1
    zone_journals = []
    for journal, count in sorted_journals:
        cumulative += count
        zone_journals.append({"name": journal, "count": count})
        if cumulative >= third * zone_num and zone_num < 3:
            zones.append({"zone": zone_num, "journals": zone_journals, "article_count": cumulative})
            zone_journals = []
            zone_num += 1
    if zone_journals:
        zones.append({"zone": zone_num, "journals": zone_journals, "article_count": total_pubs})
    return {
        "top_journals": top_journals,
        "bradford_zones": [{"zone": z["zone"], "journal_count": len(z["journals"]), "article_count": z["article_count"]} for z in zones],
        "total_journals": len(journal_counter)}
