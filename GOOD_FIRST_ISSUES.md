# Good First Contributions

The fastest way to get a PR merged into BibMedEd is to write an adapter. Each adapter below is a self-contained ~50–100 line Python file plus a test fixture. Pick one, open an [adapter request issue](.github/ISSUE_TEMPLATE/adapter_request.yml) to claim it, and ship.

Read the [adapter guide](https://ata381.github.io/BibMedEd/adapters/) first. Reference implementations: `bibmeded/app/adapters/pubmed.py` and `bibmeded/app/adapters/openalex.py` — plus `crossref.py` and `semantic_scholar.py`, which shipped in v0.2.0 and are no longer listed below.

## Open-access sources (no API key needed)

| Source | API | Notes | Status |
|---|---|---|---|
| **Europe PMC** | <https://europepmc.org/RestfulWebService> | Broader life-sciences coverage than PubMed, includes preprints. | [#7](https://github.com/ata381/BibMedEd/issues/7) |
| **arXiv** | <https://info.arxiv.org/help/api/index.html> | Preprints relevant to med-AI / informatics papers. | [#9](https://github.com/ata381/BibMedEd/issues/9) |
| **CORE** | <https://core.ac.uk/services/api> | Aggregates open-access repositories worldwide. Free key by email. | [#12](https://github.com/ata381/BibMedEd/issues/12) |
| **BASE (Bielefeld)** | <https://www.base-search.net/about/en/about_develop.php> | Massive OA aggregator, strong European coverage. | [#13](https://github.com/ata381/BibMedEd/issues/13) |
| **DOAJ** | <https://doaj.org/api/v3/docs> | Directory of Open Access Journals — useful for OA-only filters. | [#10](https://github.com/ata381/BibMedEd/issues/10) |
| **OpenCitations** | <https://opencitations.net/index/api/v2> | Citation links by DOI; pairs well with CrossRef. | [#11](https://github.com/ata381/BibMedEd/issues/11) |

## API-key sources (free tier available)

| Source | API | Notes | Status |
|---|---|---|---|
| **Lens.org Scholarly** | <https://docs.api.lens.org/> | Scholarly + patent metadata. Free academic tier. | [#14](https://github.com/ata381/BibMedEd/issues/14) |
| **Dimensions** | <https://docs.dimensions.ai/dsl/> | Strong grant + clinical-trial linkage. Free for non-commercial. | Open |

## Institutional / paid sources

| Source | API | Notes | Status |
|---|---|---|---|
| **Scopus (Elsevier)** | <https://dev.elsevier.com/sc_apis.html> | Most-requested commercial source. Requires institutional key. | Open |
| **Web of Science** | <https://developer.clarivate.com/apis/wos> | Citation-network gold standard. Institutional access. | Open |

## Non-adapter starter tasks

- **PRISMA flow diagram export** — [#15](https://github.com/ata381/BibMedEd/issues/15)
- **i18n scaffold + Turkish locale** — [#16](https://github.com/ata381/BibMedEd/issues/16)
- **Search CLI `--dry-run` for cost estimation** — [#17](https://github.com/ata381/BibMedEd/issues/17)
- **Locale-aware date parsing** in `app/services/cleaning.py` — currently assumes ISO; some adapters emit `DD-MM-YYYY`.
- **Improve the empty-state copy** in the frontend project dashboard (`bibmeded/frontend/app/projects/`).

## Claiming and shipping

1. Comment on (or open) an issue for the item you want.
2. Fork → branch off `master` → implement → `pytest -q`.
3. Open a PR using the template. Tag the issue with `Closes #N`.
4. Expect review within a week. PRs that include tests get merged faster.
