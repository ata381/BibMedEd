import math
from collections import Counter
from itertools import combinations

import networkx as nx
from sqlalchemy.orm import Session, joinedload
from app.models import Publication, SearchProject
from app.analysis.utils import graph_to_d3


def _compute_indices(citations: list[int], pub_count: int) -> dict[str, float | int]:
    """Compute h, g, and e indices from a list of per-publication citations.

    Precondition: this function sorts internally — callers do not need to pre-sort.

    - h-index (Hirsch, 2005): largest h such that h papers each have >= h citations.
    - g-index (Egghe, 2006): largest g such that the top g papers have >= g^2 cumulative
      citations; rewards a small number of highly-cited outliers more than h-index.
    - e-index (Zhang, 2009): sqrt of the excess citations of the h-core beyond h^2,
      capturing impact concentrated in the most-cited papers.

    Not implemented: hI-norm (requires per-paper author count, which the current ORM does
    not track at the publication-author relationship). Excluded from the response rather
    than returned as a placeholder.
    """
    if not citations:
        return {"h_index": 0, "g_index": 0, "e_index": 0.0}
    sorted_cites = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(sorted_cites, start=1):
        if c >= i:
            h = i
        else:
            break
    g = 0
    cumulative = 0
    for i, c in enumerate(sorted_cites, start=1):
        cumulative += c
        if cumulative >= i * i:
            g = i
        else:
            break
    h_core = sorted_cites[:h]
    excess = sum(h_core) - h * h
    e_index = round(math.sqrt(excess), 2) if excess > 0 else 0.0
    return {"h_index": h, "g_index": g, "e_index": e_index}


def analyze_authors(db: Session, project_id: int) -> dict:
    """Compute per-author productivity and the project's co-authorship network.

    Returns:
        {
          "top_authors": [
            {
              "id": int, "name": str, "orcid": str | None,
              "pub_count": int, "citation_sum": int,
              "h_index": int, "g_index": int, "e_index": float,
            },
            ...  # top 20, sorted by (h_index, citation_sum, pub_count) desc
          ],
          "coauthorship_network": {
            "nodes": [{"id": int, "name": str, "pub_count": int}, ...],
            "links": [{"source": int, "target": int, "weight": int}, ...],
          },
          "total_authors": int,
        }

    The indices are **corpus-scoped**, not career-wide — they reflect the author's
    impact within this project's deduplicated record set only. Cite as
    "h-index within the queried corpus" in any published methods section.
    """
    project = db.get(SearchProject, project_id)
    if not project:
        return {"top_authors": [], "coauthorship_network": {"nodes": [], "links": []}, "total_authors": 0}
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"top_authors": [], "coauthorship_network": {"nodes": [], "links": []}, "total_authors": 0}
    pubs = (
        db.query(Publication)
        .options(joinedload(Publication.authors))
        .filter(Publication.query_id.in_(query_ids), Publication.excluded == False)
        .all()
    )
    author_stats: dict[int, dict] = {}
    author_citations: dict[int, list[int]] = {}
    coauthor_counter: Counter = Counter()
    for pub in pubs:
        author_ids = [a.id for a in pub.authors]
        for author in pub.authors:
            if author.id not in author_stats:
                author_stats[author.id] = {
                    "id": author.id,
                    "name": author.name,
                    "pub_count": 0,
                    "citation_sum": 0,
                    "orcid": author.orcid,
                }
                author_citations[author.id] = []
            cites = pub.citation_count or 0
            author_stats[author.id]["pub_count"] += 1
            author_stats[author.id]["citation_sum"] += cites
            author_citations[author.id].append(cites)
        coauthor_counter.update(tuple(sorted([a1, a2])) for a1, a2 in combinations(author_ids, 2))

    for aid, stats in author_stats.items():
        stats.update(_compute_indices(author_citations[aid], stats["pub_count"]))

    top_authors = sorted(
        author_stats.values(),
        key=lambda x: (x["h_index"], x["citation_sum"], x["pub_count"]),
        reverse=True,
    )[:20]
    G = nx.Graph()
    for aid, stats in author_stats.items():
        G.add_node(aid, name=stats["name"], pub_count=stats["pub_count"])
    for (a1, a2), weight in coauthor_counter.items():
        G.add_edge(a1, a2, weight=weight)
    return {"top_authors": top_authors, "coauthorship_network": graph_to_d3(G), "total_authors": len(author_stats)}
