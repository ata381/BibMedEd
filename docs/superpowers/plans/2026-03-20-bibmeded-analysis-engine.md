# BibMedEd Analysis Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 6 bibliometric analysis modules that compute metrics and network data from stored publications, plus the API endpoints to trigger and retrieve analysis results.

**Architecture:** Each analysis module is a standalone Python function that takes a SQLAlchemy session + project_id and returns a JSON-serializable dict. Results are cached in the AnalysisRun table. A single analysis router exposes all modules via `/api/projects/{id}/analysis/{type}`.

**Tech Stack:** NetworkX (networks), pandas (aggregation), scikit-learn (clustering), scipy (statistics)

**Spec:** `docs/superpowers/specs/2026-03-20-bibmeded-design.md`
**Depends on:** Plan 1 (Backend Foundation) — complete

---

## File Structure

```
bibmeded/app/
├── analysis/
│   ├── __init__.py              # Re-exports all analysis functions
│   ├── publications.py          # Publication trends analysis
│   ├── authors.py               # Author analysis + co-authorship network
│   ├── countries.py             # Country & institution analysis
│   ├── keywords.py              # Keyword co-occurrence + themes
│   ├── citations.py             # Citation analysis
│   ├── journals.py              # Journal analysis + Bradford's Law
│   └── utils.py                 # Shared helpers (network to JSON, etc.)
├── routers/
│   └── analysis.py              # Analysis API router
└── schemas/
    └── analysis.py              # Analysis response schemas

bibmeded/tests/
├── test_analysis_publications.py
├── test_analysis_authors.py
├── test_analysis_countries.py
├── test_analysis_keywords.py
├── test_analysis_citations.py
├── test_analysis_journals.py
└── test_routers_analysis.py
```

---

## Task 1: Analysis Utils + Publication Trends

**Files:**
- Create: `app/analysis/__init__.py`
- Create: `app/analysis/utils.py`
- Create: `app/analysis/publications.py`
- Create: `tests/test_analysis_publications.py`

### app/analysis/utils.py

Shared helper to convert NetworkX graphs to D3-compatible JSON:

```python
import networkx as nx

def graph_to_d3(G: nx.Graph) -> dict:
    """Convert NetworkX graph to {nodes: [...], links: [...]} for D3.js."""
    nodes = [{"id": n, **G.nodes[n]} for n in G.nodes()]
    links = [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)]
    return {"nodes": nodes, "links": links}
```

### app/analysis/publications.py

```python
import pandas as pd
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject

def analyze_publication_trends(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}

    pubs = db.query(Publication.year, Publication.id).filter(
        Publication.query_id.in_(query_ids), Publication.year.isnot(None)
    ).all()

    if not pubs:
        return {"yearly_counts": [], "total": 0, "growth_rates": [], "cumulative": []}

    df = pd.DataFrame(pubs, columns=["year", "id"])
    yearly = df.groupby("year").size().reset_index(name="count").sort_values("year")

    yearly_counts = [{"year": int(r["year"]), "count": int(r["count"])} for _, r in yearly.iterrows()]

    # Growth rates
    counts = yearly["count"].tolist()
    growth_rates = []
    for i in range(1, len(counts)):
        prev = counts[i - 1]
        rate = ((counts[i] - prev) / prev * 100) if prev > 0 else 0
        growth_rates.append({"year": int(yearly.iloc[i]["year"]), "rate": round(rate, 1)})

    # Cumulative
    cumulative = []
    total = 0
    for _, r in yearly.iterrows():
        total += int(r["count"])
        cumulative.append({"year": int(r["year"]), "cumulative": total})

    return {
        "yearly_counts": yearly_counts,
        "total": len(pubs),
        "growth_rates": growth_rates,
        "cumulative": cumulative,
    }
```

### tests/test_analysis_publications.py

```python
from app.models import Publication, SearchProject, SearchQuery
from app.analysis.publications import analyze_publication_trends

def test_publication_trends(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    for i, year in enumerate([2022, 2022, 2023, 2023, 2023, 2024]):
        db.add(Publication(pmid=f"trend{i}", title=f"P{i}", year=year, query_id=query.id))
    db.commit()

    result = analyze_publication_trends(db, project.id)
    assert result["total"] == 6
    assert len(result["yearly_counts"]) == 3
    assert result["yearly_counts"][0] == {"year": 2022, "count": 2}
    assert result["yearly_counts"][1] == {"year": 2023, "count": 3}
    assert len(result["cumulative"]) == 3
    assert result["cumulative"][-1]["cumulative"] == 6

def test_publication_trends_empty(db):
    project = SearchProject(name="Empty")
    db.add(project)
    db.commit()
    result = analyze_publication_trends(db, project.id)
    assert result["total"] == 0
    assert result["yearly_counts"] == []
```

---

## Task 2: Author Analysis + Co-authorship Network

**Files:**
- Create: `app/analysis/authors.py`
- Create: `tests/test_analysis_authors.py`

### app/analysis/authors.py

```python
import networkx as nx
import pandas as pd
from itertools import combinations
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject, Author, publication_authors
from app.analysis.utils import graph_to_d3

def analyze_authors(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"top_authors": [], "coauthorship_network": {"nodes": [], "links": []}, "total_authors": 0}

    # Get all publications with their authors
    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids)).all()

    author_stats = {}  # author_id -> {name, pub_count, citation_sum}
    coauthor_pairs = []  # list of (author_id, author_id) pairs per paper

    for pub in pubs:
        author_ids = [a.id for a in pub.authors]
        for author in pub.authors:
            if author.id not in author_stats:
                author_stats[author.id] = {"name": author.name, "pub_count": 0, "citation_sum": 0, "orcid": author.orcid}
            author_stats[author.id]["pub_count"] += 1
            author_stats[author.id]["citation_sum"] += pub.citation_count or 0

        # Co-authorship pairs
        for a1, a2 in combinations(author_ids, 2):
            pair = tuple(sorted([a1, a2]))
            coauthor_pairs.append(pair)

    # Top authors by publication count
    top_authors = sorted(author_stats.values(), key=lambda x: x["pub_count"], reverse=True)[:20]

    # Co-authorship network
    G = nx.Graph()
    for aid, stats in author_stats.items():
        G.add_node(aid, name=stats["name"], pub_count=stats["pub_count"])

    edge_weights = {}
    for pair in coauthor_pairs:
        edge_weights[pair] = edge_weights.get(pair, 0) + 1
    for (a1, a2), weight in edge_weights.items():
        G.add_edge(a1, a2, weight=weight)

    return {
        "top_authors": top_authors,
        "coauthorship_network": graph_to_d3(G),
        "total_authors": len(author_stats),
    }
```

### tests/test_analysis_authors.py

```python
from app.models import Author, Publication, SearchProject, SearchQuery
from app.analysis.authors import analyze_authors

def test_author_analysis(db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()

    a1 = Author(name="Smith, John", name_normalized="smith john")
    a2 = Author(name="Chen, Li", name_normalized="chen li")
    a3 = Author(name="Patel, Raj", name_normalized="patel raj")

    pub1 = Publication(pmid="auth1", title="Paper 1", year=2024, citation_count=10, query_id=query.id)
    pub1.authors.extend([a1, a2])
    pub2 = Publication(pmid="auth2", title="Paper 2", year=2024, citation_count=5, query_id=query.id)
    pub2.authors.extend([a1, a3])
    db.add_all([pub1, pub2])
    db.commit()

    result = analyze_authors(db, project.id)
    assert result["total_authors"] == 3
    assert result["top_authors"][0]["name"] == "Smith, John"
    assert result["top_authors"][0]["pub_count"] == 2
    assert len(result["coauthorship_network"]["nodes"]) == 3
    assert len(result["coauthorship_network"]["links"]) >= 2

def test_author_analysis_empty(db):
    project = SearchProject(name="Empty")
    db.add(project)
    db.commit()
    result = analyze_authors(db, project.id)
    assert result["total_authors"] == 0
```

---

## Task 3: Country & Institution Analysis

**Files:**
- Create: `app/analysis/countries.py`
- Create: `tests/test_analysis_countries.py`

### app/analysis/countries.py

```python
import networkx as nx
from collections import Counter
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject, Affiliation, Author, author_affiliations, publication_authors
from app.analysis.utils import graph_to_d3

def analyze_countries(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
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

        # International collaboration pairs
        countries_list = sorted(pub_countries)
        from itertools import combinations
        for c1, c2 in combinations(countries_list, 2):
            collab_pairs.append((c1, c2))

    country_counts = [{"country": c, "count": n} for c, n in country_counter.most_common(30)]
    institution_counts = [{"institution": i, "count": n} for i, n in institution_counter.most_common(20)]

    # Collaboration network
    G = nx.Graph()
    for c, n in country_counter.items():
        G.add_node(c, count=n)
    edge_weights = Counter(collab_pairs)
    for (c1, c2), weight in edge_weights.items():
        G.add_edge(c1, c2, weight=weight)

    return {
        "country_counts": country_counts,
        "institution_counts": institution_counts,
        "collaboration_network": graph_to_d3(G),
    }
```

---

## Task 4: Keyword & Theme Analysis

**Files:**
- Create: `app/analysis/keywords.py`
- Create: `tests/test_analysis_keywords.py`

### app/analysis/keywords.py

```python
import networkx as nx
from collections import Counter
from itertools import combinations
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject, Keyword
from app.analysis.utils import graph_to_d3

def analyze_keywords(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"top_keywords": [], "cooccurrence_network": {"nodes": [], "links": []}, "keyword_trends": []}

    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids)).all()

    keyword_counter = Counter()
    keyword_year = {}  # keyword -> {year: count}
    cooccurrence_pairs = []

    for pub in pubs:
        kw_terms = [kw.term for kw in pub.keywords]
        for term in kw_terms:
            keyword_counter[term] += 1
            if term not in keyword_year:
                keyword_year[term] = Counter()
            if pub.year:
                keyword_year[term][pub.year] += 1

        for t1, t2 in combinations(sorted(set(kw_terms)), 2):
            cooccurrence_pairs.append((t1, t2))

    top_keywords = [{"term": t, "count": n} for t, n in keyword_counter.most_common(30)]

    # Co-occurrence network
    G = nx.Graph()
    for term, count in keyword_counter.items():
        G.add_node(term, count=count)
    edge_weights = Counter(cooccurrence_pairs)
    for (t1, t2), weight in edge_weights.most_common(200):
        G.add_edge(t1, t2, weight=weight)

    # Keyword trends (top 10 keywords over time)
    top_10_terms = [t for t, _ in keyword_counter.most_common(10)]
    keyword_trends = []
    for term in top_10_terms:
        yearly = keyword_year.get(term, {})
        trend = [{"year": int(y), "count": int(c)} for y, c in sorted(yearly.items())]
        keyword_trends.append({"term": term, "trend": trend})

    return {
        "top_keywords": top_keywords,
        "cooccurrence_network": graph_to_d3(G),
        "keyword_trends": keyword_trends,
    }
```

---

## Task 5: Citation Analysis

**Files:**
- Create: `app/analysis/citations.py`
- Create: `tests/test_analysis_citations.py`

### app/analysis/citations.py

```python
import networkx as nx
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject, Citation
from app.analysis.utils import graph_to_d3

def analyze_citations(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"most_cited": [], "citation_network": {"nodes": [], "links": []}, "total_citations": 0}

    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids)).all()
    pub_ids = {p.id for p in pubs}
    pmid_map = {p.id: p for p in pubs}

    # Most cited papers (from iCite data)
    most_cited = sorted(
        [{"pmid": p.pmid, "title": p.title, "year": p.year, "citation_count": p.citation_count or 0}
         for p in pubs],
        key=lambda x: x["citation_count"], reverse=True
    )[:20]

    total_citations = sum(p.citation_count or 0 for p in pubs)

    # Citation network (within result set)
    citations = db.query(Citation).filter(
        Citation.citing_publication_id.in_(pub_ids),
        Citation.cited_publication_id.in_(pub_ids),
    ).all()

    G = nx.DiGraph()
    for p in pubs:
        G.add_node(p.id, pmid=p.pmid, title=p.title[:60], year=p.year, citations=p.citation_count or 0)
    for c in citations:
        G.add_edge(c.citing_publication_id, c.cited_publication_id)

    # Bibliographic coupling (papers that cite the same references)
    coupling = {}
    citing_map = {}
    for c in citations:
        if c.citing_publication_id not in citing_map:
            citing_map[c.citing_publication_id] = set()
        citing_map[c.citing_publication_id].add(c.cited_publication_id)

    return {
        "most_cited": most_cited,
        "citation_network": graph_to_d3(G),
        "total_citations": total_citations,
    }
```

---

## Task 6: Journal Analysis + Bradford's Law

**Files:**
- Create: `app/analysis/journals.py`
- Create: `tests/test_analysis_journals.py`

### app/analysis/journals.py

```python
import math
from collections import Counter
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject, Journal

def analyze_journals(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return {"top_journals": [], "bradford_zones": [], "total_journals": 0}

    pubs = db.query(Publication).filter(Publication.query_id.in_(query_ids)).all()

    journal_counter = Counter()
    journal_citations = Counter()
    for pub in pubs:
        if pub.journal:
            journal_counter[pub.journal.name] += 1
            journal_citations[pub.journal.name] += pub.citation_count or 0

    top_journals = [
        {"name": j, "pub_count": n, "avg_citations": round(journal_citations[j] / n, 1) if n > 0 else 0}
        for j, n in journal_counter.most_common(20)
    ]

    # Bradford's Law zones
    # Zone 1 (core): ~1/3 of articles from few journals
    # Zone 2 (middle): ~1/3 from more journals
    # Zone 3 (periphery): ~1/3 from many journals
    sorted_journals = journal_counter.most_common()
    total_pubs = sum(n for _, n in sorted_journals)
    third = total_pubs / 3

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
        "total_journals": len(journal_counter),
    }
```

---

## Task 7: Analysis __init__.py + API Router + Tests

**Files:**
- Create: `app/analysis/__init__.py`
- Create: `app/schemas/analysis.py`
- Create: `app/routers/analysis.py`
- Update: `app/main.py` (add analysis router)
- Create: `tests/test_routers_analysis.py`

### app/analysis/__init__.py

```python
from app.analysis.publications import analyze_publication_trends
from app.analysis.authors import analyze_authors
from app.analysis.countries import analyze_countries
from app.analysis.keywords import analyze_keywords
from app.analysis.citations import analyze_citations
from app.analysis.journals import analyze_journals

ANALYSIS_FUNCTIONS = {
    "publications": analyze_publication_trends,
    "authors": analyze_authors,
    "countries": analyze_countries,
    "keywords": analyze_keywords,
    "citations": analyze_citations,
    "journals": analyze_journals,
}
```

### app/schemas/analysis.py

```python
from datetime import datetime
from pydantic import BaseModel
from typing import Any

class AnalysisRequest(BaseModel):
    analysis_type: str

class AnalysisResponse(BaseModel):
    id: int
    project_id: int
    analysis_type: str
    results: Any
    created_at: datetime
    model_config = {"from_attributes": True}
```

### app/routers/analysis.py

```python
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SearchProject, AnalysisRun
from app.analysis import ANALYSIS_FUNCTIONS
from app.schemas.analysis import AnalysisResponse

router = APIRouter(prefix="/api/projects/{project_id}/analysis", tags=["analysis"])

@router.post("/{analysis_type}", response_model=AnalysisResponse)
def run_analysis(project_id: int, analysis_type: str, db: Session = Depends(get_db)):
    if analysis_type not in ANALYSIS_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown analysis type: {analysis_type}")
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    func = ANALYSIS_FUNCTIONS[analysis_type]
    results = func(db, project_id)

    run = AnalysisRun(
        project_id=project_id,
        analysis_type=analysis_type,
        results=json.dumps(results),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return AnalysisResponse(
        id=run.id, project_id=run.project_id, analysis_type=run.analysis_type,
        results=results, created_at=run.created_at,
    )

@router.get("/{analysis_type}", response_model=AnalysisResponse)
def get_analysis(project_id: int, analysis_type: str, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(
        AnalysisRun.project_id == project_id,
        AnalysisRun.analysis_type == analysis_type,
    ).order_by(AnalysisRun.created_at.desc()).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis not found. Run it first.")
    return AnalysisResponse(
        id=run.id, project_id=run.project_id, analysis_type=run.analysis_type,
        results=json.loads(run.results), created_at=run.created_at,
    )
```

Register in main.py:
```python
from app.routers import projects, search, publications, analysis
app.include_router(analysis.router)
```

---
