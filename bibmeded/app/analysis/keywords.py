import networkx as nx
from collections import Counter
from itertools import combinations
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject
from app.analysis.utils import graph_to_d3

def analyze_keywords(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return {"top_keywords": [], "cooccurrence_network": {"nodes": [], "links": []}, "keyword_trends": []}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"top_keywords": [], "cooccurrence_network": {"nodes": [], "links": []}, "keyword_trends": []}
    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids), Publication.excluded == False).all()
    keyword_counter = Counter()
    keyword_year = {}
    display_by_normalized: dict[str, str] = {}
    cooccurrence_pairs = []
    for pub in pubs:
        kw_terms = [kw.term.strip() for kw in pub.keywords if kw.term and kw.term.strip()]
        normalized_terms = [term.lower() for term in kw_terms]

        unique_terms: set[str] = set()
        for normalized, original in zip(normalized_terms, kw_terms):
            display_by_normalized.setdefault(normalized, original)
            unique_terms.add(normalized)
            keyword_counter[normalized] += 1
            if normalized not in keyword_year:
                keyword_year[normalized] = Counter()
            if pub.year:
                keyword_year[normalized][pub.year] += 1

        for t1, t2 in combinations(sorted(unique_terms), 2):
            cooccurrence_pairs.append((t1, t2))

    top_keywords = [
        {"term": display_by_normalized.get(t, t), "count": n}
        for t, n in keyword_counter.most_common(30)
    ]
    G = nx.Graph()
    for term, count in keyword_counter.items():
        G.add_node(term, count=count, label=display_by_normalized.get(term, term))
    for (t1, t2), weight in Counter(cooccurrence_pairs).most_common(200):
        G.add_edge(t1, t2, weight=weight)
    top_10 = [t for t, _ in keyword_counter.most_common(10)]
    keyword_trends = []
    for term in top_10:
        yearly = keyword_year.get(term, {})
        keyword_trends.append(
            {
                "term": display_by_normalized.get(term, term),
                "trend": [{"year": int(y), "count": int(c)} for y, c in sorted(yearly.items())],
            }
        )
    return {"top_keywords": top_keywords, "cooccurrence_network": graph_to_d3(G), "keyword_trends": keyword_trends}
