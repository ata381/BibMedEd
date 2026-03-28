import networkx as nx
from collections import Counter
from itertools import combinations
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject
from app.analysis.utils import graph_to_d3

def analyze_countries(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return {"country_counts": [], "institution_counts": [], "collaboration_network": {"nodes": [], "links": []}}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"country_counts": [], "institution_counts": [], "collaboration_network": {"nodes": [], "links": []}}
    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids)).all()
    country_counter = Counter()
    institution_counter = Counter()
    collab_pairs = []
    for pub in pubs:
        pub_countries = set()
        for author in pub.authors:
            for aff in author.affiliations:
                if aff.country:
                    country_counter[aff.country] += 1
                    pub_countries.add(aff.country)
                institution_counter[aff.name] += 1
        for c1, c2 in combinations(sorted(pub_countries), 2):
            collab_pairs.append((c1, c2))
    country_counts = [{"country": c, "count": n} for c, n in country_counter.most_common(30)]
    institution_counts = [{"institution": i, "count": n} for i, n in institution_counter.most_common(20)]
    G = nx.Graph()
    for c, n in country_counter.items():
        G.add_node(c, count=n)
    for (c1, c2), weight in Counter(collab_pairs).items():
        G.add_edge(c1, c2, weight=weight)
    return {"country_counts": country_counts, "institution_counts": institution_counts, "collaboration_network": graph_to_d3(G)}
