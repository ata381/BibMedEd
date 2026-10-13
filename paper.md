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
date: 14 October 2026
bibliography: paper.bib
---

# Summary

`BibMedEd` is an open-source web application that unifies multi-database bibliographic search, automated deduplication, bibliometric analysis, network visualisation, and reproducible methodology logging in a single self-hostable platform. It is designed for medical-education researchers who currently assemble systematic reviews and scientometric studies from a fragmented toolchain of PubMed search, Covidence [@covidence], VOSviewer [@vanEck2010vosviewer], CiteSpace [@chen2006citespace], and ad-hoc Excel processing. `BibMedEd` replaces that workflow with one application: a researcher specifies a query, selects one or more data sources, and obtains a deduplicated record set together with six analysis modules (publications over time, author productivity, country distribution, keyword co-occurrence, citation impact, and journal ranking), interactive D3.js network graphs, and a citable text-format methodology log that records every pipeline step for inclusion in the study's Methods section.

The platform is built on FastAPI, SQLAlchemy 2.0, Celery, PostgreSQL, and Redis on the backend, with a Next.js 16 / React 19 / D3.js frontend. Data ingestion uses a small plug-and-play adapter interface: each new bibliographic source is a Python class implementing `search()` and `fetch()` methods that map the source's native record format to a universal `RawRecord` dataclass. Five adapters ship with the platform — PubMed (via NCBI E-utilities), OpenAlex [@priem2022openalex], CrossRef, Semantic Scholar [@kinney2023semanticscholar], and Lens.org Scholarly — and additional adapters can be contributed without modifying core code; the registry auto-discovers any `BaseSourceAdapter` subclass placed in `bibmeded/adapters/`.

**Cross-source deduplication.** Records are deduplicated in two stages. First, identifiers are normalised: DOIs are lowercased and stripped of `https://doi.org/`, `doi:`, and `http://doi.org/` prefixes; PMIDs are whitespace-trimmed. Second, a single in-memory pass over each fetched batch removes records whose normalised DOI or PMID has already been seen within the current search run. The first occurrence is retained, later occurrences are dropped, and a per-field breakdown (`removed_by={"doi": n, "pmid": m}`) is written to the methodology log so the dedup decision is fully auditable. Identifier priority is DOI first, then PMID; records that share neither remain distinct. The fixture-based test suite covers both single-source and cross-source dedup paths.

# Statement of need

Bibliometric analysis is increasingly central to medical-education research, supporting systematic reviews [@gusenbauer2020academic], curriculum-evidence synthesis, and research-impact evaluation. The dominant tooling, however, is either commercial (Covidence, Web of Science, Scopus, Dimensions), single-source (PubMed-only search interfaces), or analysis-only and not integrated with retrieval (VOSviewer, CiteSpace, Bibliometrix [@aria2017bibliometrix]). Researchers therefore stitch together a workflow across four or more tools, manually deduplicating records and reconciling identifier schemes between systems. This is time-consuming, error-prone, and — critically for systematic-review reproducibility under PRISMA 2020 [@page2021prisma] — difficult to document with the fidelity required for a Methods section.

`BibMedEd` combines retrieval, deduplication, screening, analysis, visualisation and methodology logging behind one web interface that runs with a single `docker compose up` on commodity hardware, with no external services beyond optional NCBI and OpenAlex API keys.

The methodology-log feature is, to the authors' knowledge, novel among open bibliometric tools. Every adapter call, deduplication decision, filter, and analysis run is recorded with timestamps, queries, and record counts, and can be exported as a plain-text file that researchers cite as supplementary material in their published reviews. This directly supports PRISMA 2020 item 7 (search strategy reporting) and item 9 (deduplication process), the search-reporting items of PRISMA-S [@rethlefsen2021prismas] and the Methods items of BIBLIO [@montazeri2023biblio] without manual transcription.

# State of the field

Bibliometric studies in health-professions education are usually built from a Web of Science or Scopus export analysed in VOSviewer [@vanEck2010vosviewer], CiteSpace [@chen2006citespace] or Bibliometrix [@aria2017bibliometrix]; systematic reviews add Covidence [@covidence] or Rayyan for screening. These tools are mature and `BibMedEd` does not replace them where they are strong: VOSviewer and Bibliometrix import OpenAlex, Crossref and PubMed data directly and draw publication-quality maps, Bibliometrix implements a broader battery of analyses, and Covidence offers dual-reviewer screening with conflict resolution. `pyBibX` [@pereira2024pybibx] provides Python-native analysis over a pre-collected `.bib` file.

Two gaps remain. First, none of these tools records what was done. The search strings, dates, record counts, deduplication rules and screening decisions that the BIBLIO guideline for bibliometric reviews [@montazeri2023biblio] and PRISMA-S for literature searches [@rethlefsen2021prismas] ask for are reconstructed by hand, and a 2024 metaresearch study found that only about a tenth of systematic-review searches could be reproduced from the published report [@rethlefsen2024reproducible]. Second, the open indexes that make licence-free bibliometrics possible, OpenAlex [@priem2022openalex] above all, are reachable through APIs and R or Python packages rather than through an interface a non-programmer can use. `BibMedEd` is built for those two gaps and hands its corpus on to the existing tools: it exports Web of Science plain text that VOSviewer and Bibliometrix read, so a study can be retrieved, deduplicated, screened and logged in `BibMedEd` and still drawn in the tool the field trusts. Contributing this to VOSviewer or Bibliometrix was not an option, since neither is a retrieval or screening tool and neither keeps a per-decision log.

# Software design

`BibMedEd` is organised around four components:

1. A **FastAPI backend** exposing REST endpoints for projects, searches, analyses, and exports.
2. A **Celery worker pool** that runs long-running search and analysis pipelines asynchronously, with live progress reported to the frontend via polling.
3. An **adapter registry** that auto-discovers any `BaseSourceAdapter` subclass in `bibmeded/adapters/`, making the system extensible without touching core code.
4. A **Next.js frontend** providing the search UI, project dashboard, results table, interactive network graphs, and export manager.

Analysis modules use NetworkX [@hagberg2008networkx] for graph computations and lightweight standard-library aggregations (`collections.Counter`) to keep the deployment footprint small. Network visualisations are rendered client-side with D3.js to enable interactive exploration of co-authorship and keyword co-occurrence structures. Per-author productivity exposes the h-index [@hirsch2005index], g-index [@egghe2006theory], and e-index [@zhang2009eindex]; field maturity is classified by fitting a logistic-growth curve to the cumulative publication-year series via SciPy's Levenberg-Marquardt routine and bucketing the result into emerging / growing / mature / saturating phases.

**Design trade-offs.** Three choices shape the system. First, the methodology log is written by the pipeline itself, in the same transaction as the data it describes, rather than reconstructed afterwards from database state: every search, fetch, deduplication, enrichment, exclusion and bulk-exclusion step is a row, and the exports only read those rows. This costs a write per step and a schema that must evolve with the pipeline, and buys a log that cannot disagree with the corpus. Second, deduplication is exact-match on normalised DOI and PMID. Fuzzy title matching finds more duplicates but produces decisions a reader cannot audit, so the exact rule is stated in the log and residual duplicates are left to screening, where a reviewer's removal is itself logged; fuzzy matching with logged decisions is the next planned step. Third, the server is single-tenant and has no accounts. It is meant to run on a lab machine behind the institution's own login, which keeps deployment to one `docker compose up` and keeps each screening decision attributable to a stated reviewer label rather than to an authentication layer the project would have to get right. PostgreSQL and Celery carry concurrent searches in production; the test suite runs the same code on SQLite so contributors need no services.

**Operational limits.** The default per-search ceiling is 2,000 records (configurable up to 10,000 in the API). This ceiling is a deliberate trade-off, not a memory bound: PubMed E-utilities and OpenAlex permit larger windowed queries, but a single 2,000-record search is the largest set most journal-quality systematic reviews ingest in one pass without violating courtesy rate-limits or losing fine-grained control over the methodology log. For corpora above this size, researchers should split queries by date range and merge results outside `BibMedEd`; the cross-source dedup pass then runs over the merged records when ingested into a single project. Results pages surface a warning when the upstream result count exceeds the fetched ceiling so truncation is never silent.

**Programmatic access.** The FastAPI app exposes an OpenAPI specification at `/openapi.json` with interactive Swagger UI at `/docs` and ReDoc at `/redoc`. Analysis responses are stamped with a `schema_version` field so downstream pipelines can pin against a known shape; bulk-export endpoints include CSV, RIS, JSON (versioned schema), the PRISMA SVG, a plain-text methodology log, and a single-click `.zip` bundle of all five plus a `MANIFEST.txt`.

# Research impact statement

`BibMedEd` has no published research use yet; this section states what exists rather than what is hoped for. The repository has been public and under continuous development since March 2026 (189 commits by 10 contributors, a Zenodo DOI per release, continuous integration on every change). External contributors have added the command-line search workflow, the publication-growth summary, pagination and export fixes, and the PubMed request identification; two further contributor pull requests (BibTeX export, affiliation-based country extraction) are in review. The near-term path to impact is specific: the first study on the platform, an open-data (OpenAlex and PubMed) replication of a published Web of Science-only bibliometric analysis in health-professions education reported with the BIBLIO checklist, is the next planned step and needs a collaborating group in the field, and the platform's outputs (methodology log, PRISMA diagram, screening-decision log, Web of Science export) are designed to be the supplementary material of exactly the studies whose reporting the field is asking to improve.

# AI usage disclosure

`BibMedEd` is built and maintained largely by generative AI under the author's direction. From the first commit (March 2026) the code, tests and documentation have been written mostly by Anthropic Claude models operated through Claude Code (Claude Sonnet 4.6 and Opus 4.6 in March and April 2026, Opus 4.7 in May 2026, and Opus 5.5, Sonnet 5.5 and Fable 5.1 from September 2026; each commit's trailer names the model), which also triages issues, reviews pull requests and prepares releases; OpenAI Codex posts an automated review on every pull request. The author sets the project's goals, directs and reviews the agents' work, decides what is merged, and is accountable for the software. Every change passes the continuous-integration suite (backend tests, migrations, frontend build, accessibility checks and a Docker build) before it reaches the main branch, and the bibliometric methods implemented (identifier normalisation and deduplication, h-, g- and e-index, bibliographic coupling, co-citation, burst detection, logistic field-maturity fitting) are implemented from the cited literature, which readers can check against the source. This manuscript was drafted by the same AI tools from the repository and its documentation, then reviewed and edited by the author, who takes responsibility for its content.

# Acknowledgements

We thank the maintainers of the bibliographic APIs that make `BibMedEd` possible and the contributors of the open-source libraries on which the platform is built. We also thank `@BaygeldiAza` for contributing the command-line search workflow and `@landon-personal` for improving its error handling.

# References
