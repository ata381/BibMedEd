import networkx as nx
from collections import Counter
from itertools import combinations
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject
from app.analysis.utils import graph_to_d3


def _detect_bursts(
    yearly_by_term: dict[str, Counter],
    total_per_year: Counter,
    min_count: int = 3,
    surge_factor: float = 2.0,
) -> list[dict]:
    """Share-ratio heuristic for surfacing keyword burst years.

    Not a Kleinberg (2003) two-state automaton — those need a long, dense
    time series to fit reliably and over-fit on the small (<2k pubs, <15 yrs)
    corpora typical of medical-education bibliometrics. Instead:

      - For each (term, year): `share = term_count_in_year / unique_keywords_in_year`.
      - For each term: `baseline_share = mean(share) across years the term appears`.
      - A "burst" year has `share >= surge_factor * baseline_share` AND raw
        term count `>= min_count`.
      - `intensity = share / baseline_share`, dimensionless, range [surge_factor, ∞).

    The strongest burst per term is returned, ordered by intensity. Output is the
    "emerging-term" signal medical-education bibliometric papers report, with the
    method described in plain enough terms to cite without invoking Kleinberg's
    full machinery.
    """
    if not total_per_year:
        return []
    bursts: list[dict] = []
    for term, year_counts in yearly_by_term.items():
        years = sorted(year_counts.keys())
        if len(years) < 2:
            continue
        shares = []
        for y in years:
            denom = total_per_year.get(y, 0)
            shares.append(year_counts[y] / denom if denom else 0.0)
        baseline = sum(shares) / len(shares)
        if baseline <= 0:
            continue
        # Pick the strongest burst year for this term.
        best = None
        for y, share, count in zip(years, shares, (year_counts[y] for y in years)):
            if count < min_count:
                continue
            intensity = share / baseline if baseline > 0 else 0
            if intensity < surge_factor:
                continue
            if best is None or intensity > best["intensity"]:
                best = {
                    "term": term,
                    "year": int(y),
                    "count": int(count),
                    "intensity": round(intensity, 2),
                    "baseline_share": round(baseline, 4),
                }
        if best is not None:
            bursts.append(best)
    bursts.sort(key=lambda b: b["intensity"], reverse=True)
    return bursts[:15]

def analyze_keywords(db: Session, project_id: int) -> dict:
    empty = {
        "top_keywords": [],
        "cooccurrence_network": {"nodes": [], "links": []},
        "keyword_trends": [],
        "burst_terms": [],
    }
    project = db.get(SearchProject, project_id)
    if not project:
        return empty
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return empty
    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids), Publication.excluded == False).all()
    keyword_counter = Counter()
    keyword_year: dict[str, Counter] = {}
    total_per_year: Counter = Counter()
    display_by_normalized: dict[str, str] = {}
    cooccurrence_pairs = []
    cooccurrence_counter: Counter = Counter()
    for pub in pubs:
        kw_terms = [kw.term.strip() for kw in pub.keywords if kw.term and kw.term.strip()]
        # Record the original display form once per normalized variant; treat duplicate
        # terms within a single publication as one occurrence so burst-share denominators
        # don't get inflated by per-pub keyword multiplicities.
        unique_terms: set[str] = set()
        for original in kw_terms:
            normalized = original.lower()
            display_by_normalized.setdefault(normalized, original)
            unique_terms.add(normalized)
        for normalized in unique_terms:
            keyword_counter[normalized] += 1
            if normalized not in keyword_year:
                keyword_year[normalized] = Counter()
            if pub.year:
                keyword_year[normalized][pub.year] += 1
        if pub.year and unique_terms:
            total_per_year[pub.year] += len(unique_terms)

        cooccurrence_counter.update(combinations(sorted(unique_terms), 2))
    cooccurrence_pairs = cooccurrence_counter  # alias kept for the downstream block

    top_keywords = [
        {"term": display_by_normalized.get(t, t), "count": n}
        for t, n in keyword_counter.most_common(30)
    ]
    G = nx.Graph()
    for term, count in keyword_counter.items():
        G.add_node(term, count=count, label=display_by_normalized.get(term, term))
    for (t1, t2), weight in cooccurrence_pairs.most_common(200):
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
    raw_bursts = _detect_bursts(keyword_year, total_per_year)
    burst_terms = [
        {**b, "term": display_by_normalized.get(b["term"], b["term"])}
        for b in raw_bursts
    ]
    return {
        "top_keywords": top_keywords,
        "cooccurrence_network": graph_to_d3(G),
        "keyword_trends": keyword_trends,
        "burst_terms": burst_terms,
    }
