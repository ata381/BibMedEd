---
title: 'BibMedEd: An Open-Source Bibliometric Analysis Platform for Medical Education Research'
tags:
  - Python
  - bibliometrics
  - scientometrics
  - medical education
  - systematic review
  - PubMed
  - OpenAlex
  - network analysis
authors:
  - name: Ata Akillioglu
    orcid: 0009-0005-4533-4594
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 26 May 2026
bibliography: paper.bib
---

# Summary

`BibMedEd` is an open-source web application that unifies multi-database bibliographic search, automated deduplication, bibliometric analysis, network visualisation, and reproducible methodology logging in a single self-hostable platform. It is designed for medical-education researchers who currently assemble systematic reviews and scientometric studies from a fragmented toolchain of PubMed search, Covidence [@covidence], VOSviewer [@vanEck2010vosviewer], CiteSpace [@chen2006citespace], and ad-hoc Excel processing. `BibMedEd` replaces that workflow with one application: a researcher specifies a query, selects one or more data sources, and obtains a deduplicated record set together with six analysis modules (publications over time, author productivity, country distribution, keyword co-occurrence, citation impact, and journal ranking), interactive D3.js network graphs, and a citable text-format methodology log that records every pipeline step for inclusion in the study's Methods section.

The platform is built on FastAPI, SQLAlchemy 2.0, Celery, PostgreSQL, and Redis on the backend, with a Next.js 16 / React 19 / D3.js frontend. Data ingestion uses a small plug-and-play adapter interface: each new bibliographic source is a Python class implementing `search()` and `fetch()` methods that map the source's native record format to a universal `RawRecord` dataclass. Three adapters ship with the platform — PubMed (via NCBI E-utilities), OpenAlex [@priem2022openalex], and CrossRef — and additional adapters can be contributed without modifying core code.

**Cross-source deduplication.** Records are deduplicated in two stages. First, identifiers are normalised: DOIs are lowercased and stripped of `https://doi.org/`, `doi:`, and `http://doi.org/` prefixes; PMIDs are whitespace-trimmed. Second, a single in-memory pass over each fetched batch removes records whose normalised DOI or PMID has already been seen within the current search run. The first occurrence is retained, later occurrences are dropped, and a per-field breakdown (`removed_by={"doi": n, "pmid": m}`) is written to the methodology log so the dedup decision is fully auditable. Identifier priority is DOI first, then PMID; records that share neither remain distinct. The fixture-based test suite covers both single-source and cross-source dedup paths.

# Statement of need

Bibliometric analysis is increasingly central to medical-education research, supporting systematic reviews [@gusenbauer2020academic], curriculum-evidence synthesis, and research-impact evaluation. The dominant tooling, however, is either commercial (Covidence, Web of Science, Scopus, Dimensions), single-source (PubMed-only search interfaces), or analysis-only and not integrated with retrieval (VOSviewer, CiteSpace, Bibliometrix [@aria2017bibliometrix]). Researchers therefore stitch together a workflow across four or more tools, manually deduplicating records and reconciling identifier schemes between systems. This is time-consuming, error-prone, and — critically for systematic-review reproducibility under PRISMA 2020 [@page2021prisma] — difficult to document with the fidelity required for a Methods section.

A small number of open-source projects address parts of this gap. Bibliometrix [@aria2017bibliometrix] is a widely used R package for analysis but requires the user to perform retrieval and deduplication elsewhere. `pyBibX` [@pereira2024pybibx] provides Python-native analysis but similarly assumes pre-collected `.bib` input. Neither offers an integrated UI suitable for non-programmer researchers or a self-hostable web deployment. `BibMedEd` fills this gap by combining retrieval, deduplication, analysis, visualisation, and methodology logging behind a single web interface that runs with one `docker compose up` command on commodity hardware, with no external services beyond optional NCBI and OpenAlex API keys.

The methodology-log feature is, to the authors' knowledge, novel among open bibliometric tools. Every adapter call, deduplication decision, filter, and analysis run is recorded with timestamps, queries, and record counts, and can be exported as a plain-text file that researchers cite as supplementary material in their published reviews. This directly supports PRISMA 2020 item 7 (search strategy reporting) and item 9 (deduplication process) without manual transcription.

# Architecture

`BibMedEd` is organised around four components:

1. A **FastAPI backend** exposing REST endpoints for projects, searches, analyses, and exports.
2. A **Celery worker pool** that runs long-running search and analysis pipelines asynchronously, with live progress reported to the frontend via polling.
3. An **adapter registry** that auto-discovers any `BaseSourceAdapter` subclass in `app/adapters/`, making the system extensible without touching core code.
4. A **Next.js frontend** providing the search UI, project dashboard, results table, interactive network graphs, and export manager.

Analysis modules use NetworkX [@hagberg2008networkx] for graph computations and lightweight standard-library aggregations (`collections.Counter`) to keep the deployment footprint small. Network visualisations are rendered client-side with D3.js to enable interactive exploration of co-authorship and keyword co-occurrence structures. Per-author productivity exposes the h-index [@hirsch2005index], g-index [@egghe2006theory], and e-index [@zhang2009eindex]; field maturity is classified by fitting a logistic-growth curve to the cumulative publication-year series via SciPy's Levenberg-Marquardt routine and bucketing the result into emerging / growing / mature / saturating phases.

**Operational limits.** The default per-search ceiling is 2,000 records (configurable up to 10,000 in the API). This ceiling is a deliberate trade-off, not a memory bound: PubMed E-utilities and OpenAlex permit larger windowed queries, but a single 2,000-record search is the largest set most journal-quality systematic reviews ingest in one pass without violating courtesy rate-limits or losing fine-grained control over the methodology log. For corpora above this size, researchers should split queries by date range and merge results outside `BibMedEd`; the cross-source dedup pass then runs over the merged records when ingested into a single project. Results pages surface a warning when the upstream result count exceeds the fetched ceiling so truncation is never silent.

**Programmatic access.** The FastAPI app exposes an OpenAPI specification at `/openapi.json` with interactive Swagger UI at `/docs` and ReDoc at `/redoc`. Analysis responses are stamped with a `schema_version` field so downstream pipelines can pin against a known shape; bulk-export endpoints include CSV, RIS, JSON (versioned schema), the PRISMA SVG, a plain-text methodology log, and a single-click `.zip` bundle of all five plus a `MANIFEST.txt`.

# Acknowledgements

We thank the maintainers of NCBI E-utilities and OpenAlex for providing the open APIs that make `BibMedEd` possible, and the contributors of the open-source libraries on which the platform is built.

# References
