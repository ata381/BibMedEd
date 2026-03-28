import networkx as nx
from itertools import combinations
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject
from app.analysis.utils import graph_to_d3

def analyze_authors(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return {"top_authors": [], "coauthorship_network": {"nodes": [], "links": []}, "total_authors": 0}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"top_authors": [], "coauthorship_network": {"nodes": [], "links": []}, "total_authors": 0}
    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids)).all()
    author_stats = {}
    coauthor_pairs = []
    for pub in pubs:
        author_ids = [a.id for a in pub.authors]
        for author in pub.authors:
            if author.id not in author_stats:
                author_stats[author.id] = {"name": author.name, "pub_count": 0, "citation_sum": 0, "orcid": author.orcid}
            author_stats[author.id]["pub_count"] += 1
            author_stats[author.id]["citation_sum"] += pub.citation_count or 0
        for a1, a2 in combinations(author_ids, 2):
            coauthor_pairs.append(tuple(sorted([a1, a2])))
    top_authors = sorted(author_stats.values(), key=lambda x: x["pub_count"], reverse=True)[:20]
    G = nx.Graph()
    for aid, stats in author_stats.items():
        G.add_node(aid, name=stats["name"], pub_count=stats["pub_count"])
    edge_weights = {}
    for pair in coauthor_pairs:
        edge_weights[pair] = edge_weights.get(pair, 0) + 1
    for (a1, a2), weight in edge_weights.items():
        G.add_edge(a1, a2, weight=weight)
    return {"top_authors": top_authors, "coauthorship_network": graph_to_d3(G), "total_authors": len(author_stats)}
