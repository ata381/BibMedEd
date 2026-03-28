import networkx as nx
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject, Citation
from app.analysis.utils import graph_to_d3

def analyze_citations(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return {"most_cited": [], "citation_network": {"nodes": [], "links": []}, "total_citations": 0}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"most_cited": [], "citation_network": {"nodes": [], "links": []}, "total_citations": 0}
    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids)).all()
    pub_ids = {p.id for p in pubs}
    most_cited = sorted(
        [{"pmid": p.pmid, "title": p.title, "year": p.year, "citation_count": p.citation_count or 0} for p in pubs],
        key=lambda x: x["citation_count"], reverse=True)[:20]
    total_citations = sum(p.citation_count or 0 for p in pubs)
    citations = db.query(Citation).filter(Citation.citing_publication_id.in_(pub_ids), Citation.cited_publication_id.in_(pub_ids)).all()
    G = nx.DiGraph()
    for p in pubs:
        G.add_node(p.id, pmid=p.pmid, title=p.title[:60], year=p.year, citations=p.citation_count or 0)
    for c in citations:
        G.add_edge(c.citing_publication_id, c.cited_publication_id)
    return {"most_cited": most_cited, "citation_network": graph_to_d3(G), "total_citations": total_citations}
