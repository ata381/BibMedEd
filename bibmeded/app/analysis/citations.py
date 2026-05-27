"""Citation-driven analyses: most-cited table, intra-corpus citation graph,
bibliographic coupling, and co-citation networks.

Bibliographic coupling (Kessler, 1963): two publications are coupled if they
cite at least one reference in common. Coupling strength = number of shared
references. This reveals research that draws on the same intellectual base.

Co-citation (Small, 1973): two publications are co-cited if some third
publication cites both. Co-citation strength = number of citing papers.
Reveals the seminal works that newer papers ground themselves in together.

Both are computed against in-corpus publications only — the `external_references`
list on each Publication is matched against the corpus's DOIs and PMIDs (and
source-native IDs like OpenAlex `W...`). References to papers outside the
corpus are not used.
"""

from collections import Counter, defaultdict
from itertools import combinations

import networkx as nx
from sqlalchemy.orm import Session

from app.models import Citation, Publication, SearchProject
from app.analysis.utils import graph_to_d3


def _index_by_identifier(pubs: list[Publication]) -> dict[str, int]:
    """Build a {identifier → publication.id} lookup keyed on every ID a record
    might be referenced by (DOI lowercased, PMID / source_id raw)."""
    index: dict[str, int] = {}
    for pub in pubs:
        if pub.doi:
            index[pub.doi.lower()] = pub.id
        if pub.pmid:
            # `pmid` actually stores the source-native primary ID (PMID for PubMed,
            # OpenAlex W-ID for OpenAlex, DOI for CrossRef). Cover both shapes.
            index[pub.pmid] = pub.id
            index[pub.pmid.lower()] = pub.id
    return index


def _resolve_refs_in_corpus(pubs: list[Publication]) -> dict[int, set[int]]:
    """For each in-corpus pub, return the set of OTHER in-corpus pub IDs it references."""
    index = _index_by_identifier(pubs)
    refs_by_pub: dict[int, set[int]] = {}
    for pub in pubs:
        if not pub.external_references:
            refs_by_pub[pub.id] = set()
            continue
        targets: set[int] = set()
        for raw_ref in pub.external_references:
            if not raw_ref:
                continue
            target = index.get(str(raw_ref).lower()) or index.get(str(raw_ref))
            if target is not None and target != pub.id:
                targets.add(target)
        refs_by_pub[pub.id] = targets
    return refs_by_pub


def _build_coupling_pairs(refs_by_pub: dict[int, set[int]]) -> Counter:
    """Pair count weighted by shared references — two pubs that both cite paper R
    accrue +1 for each shared R."""
    cited_to_citers: dict[int, set[int]] = defaultdict(set)
    for pub_id, targets in refs_by_pub.items():
        for t in targets:
            cited_to_citers[t].add(pub_id)
    pairs: Counter = Counter()
    for citers in cited_to_citers.values():
        if len(citers) < 2:
            continue
        for a, b in combinations(sorted(citers), 2):
            pairs[(a, b)] += 1
    return pairs


def _build_cocitation_pairs(refs_by_pub: dict[int, set[int]]) -> Counter:
    """Pair count weighted by shared citing papers — two pubs co-cited by paper C
    accrue +1 for each such C."""
    pairs: Counter = Counter()
    for targets in refs_by_pub.values():
        if len(targets) < 2:
            continue
        for a, b in combinations(sorted(targets), 2):
            pairs[(a, b)] += 1
    return pairs


def _pairs_to_d3(pubs: list[Publication], pairs: Counter, top_k: int = 100) -> dict:
    if not pairs:
        return {"nodes": [], "links": []}
    # Restrict to the top_k strongest pairs and the nodes that appear in them so the
    # network stays readable for D3 force layout.
    top_pairs = pairs.most_common(top_k)
    node_ids = {n for (a, b), _ in top_pairs for n in (a, b)}
    pub_by_id = {p.id: p for p in pubs}
    G = nx.Graph()
    for pid in node_ids:
        pub = pub_by_id.get(pid)
        if pub is None:
            continue
        G.add_node(
            pid,
            pmid=pub.pmid,
            title=(pub.title or "")[:80],
            year=pub.year,
            citations=pub.citation_count or 0,
        )
    for (a, b), weight in top_pairs:
        G.add_edge(a, b, weight=weight)
    return graph_to_d3(G)


def analyze_citations(db: Session, project_id: int) -> dict:
    empty = {
        "most_cited": [],
        "citation_network": {"nodes": [], "links": []},
        "coupling_network": {"nodes": [], "links": []},
        "cocitation_network": {"nodes": [], "links": []},
        "total_citations": 0,
    }
    project = db.get(SearchProject, project_id)
    if not project:
        return empty
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return empty
    pubs = (
        db.query(Publication)
        .filter(Publication.query_id.in_(query_ids), Publication.excluded == False)
        .all()
    )
    if not pubs:
        return empty
    pub_ids = {p.id for p in pubs}
    most_cited = sorted(
        [
            {
                "pmid": p.pmid,
                "title": p.title,
                "year": p.year,
                "citation_count": p.citation_count or 0,
            }
            for p in pubs
        ],
        key=lambda x: x["citation_count"],
        reverse=True,
    )[:20]
    total_citations = sum(p.citation_count or 0 for p in pubs)

    # Intra-corpus directed citation graph (populated only if explicit Citation rows
    # exist; left here for compatibility with future ingestion improvements).
    citations = (
        db.query(Citation)
        .filter(
            Citation.citing_publication_id.in_(pub_ids),
            Citation.cited_publication_id.in_(pub_ids),
        )
        .all()
    )
    citation_graph = nx.DiGraph()
    for p in pubs:
        citation_graph.add_node(
            p.id, pmid=p.pmid, title=(p.title or "")[:60], year=p.year, citations=p.citation_count or 0
        )
    for c in citations:
        citation_graph.add_edge(c.citing_publication_id, c.cited_publication_id)

    # Bibliographic coupling + co-citation, computed from external_references.
    refs_by_pub = _resolve_refs_in_corpus(pubs)
    coupling_pairs = _build_coupling_pairs(refs_by_pub)
    cocitation_pairs = _build_cocitation_pairs(refs_by_pub)

    return {
        "most_cited": most_cited,
        "citation_network": graph_to_d3(citation_graph),
        "coupling_network": _pairs_to_d3(pubs, coupling_pairs),
        "cocitation_network": _pairs_to_d3(pubs, cocitation_pairs),
        "total_citations": total_citations,
    }
