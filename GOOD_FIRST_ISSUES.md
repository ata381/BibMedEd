# Good First Contributions

The fastest way to get a PR merged into BibMedEd is to write an adapter. Each adapter below is a self-contained ~50–100 line Python file plus a test fixture. Pick one, open an [adapter request issue](.github/ISSUE_TEMPLATE/adapter_request.yml) to claim it, and ship.

Read the [adapter guide](https://ata381.github.io/BibMedEd/adapters/) first. Reference implementations: `bibmeded/app/adapters/pubmed.py` and `bibmeded/app/adapters/openalex.py`.

## Open-access sources (no API key needed)

| Source | API | Notes | Status |
|---|---|---|---|
| **CrossRef** | <https://api.crossref.org/swagger-ui/index.html> | Authoritative DOI metadata. High value for cross-source dedup. | Open |
| **Europe PMC** | <https://europepmc.org/RestfulWebService> | Broader life-sciences coverage than PubMed, includes preprints. | Open |
| **Semantic Scholar** | <https://api.semanticscholar.org/> | Citation graph + influential-citation flags. Free tier ample. | Open |
| **arXiv** | <https://info.arxiv.org/help/api/index.html> | Preprints relevant to med-AI / informatics papers. | Open |
| **CORE** | <https://core.ac.uk/services/api> | Aggregates open-access repositories worldwide. Free key by email. | Open |
| **BASE (Bielefeld)** | <https://www.base-search.net/about/en/about_develop.php> | Massive OA aggregator, strong European coverage. | Open |
| **DOAJ** | <https://doaj.org/api/v3/docs> | Directory of Open Access Journals — useful for OA-only filters. | Open |
| **OpenCitations** | <https://opencitations.net/index/api/v2> | Citation links by DOI; pairs well with CrossRef. | Open |

## API-key sources (free tier available)

| Source | API | Notes | Status |
|---|---|---|---|
| **Lens.org Scholarly** | <https://docs.api.lens.org/> | Scholarly + patent metadata. Free academic tier. | Open |
| **Dimensions** | <https://docs.dimensions.ai/dsl/> | Strong grant + clinical-trial linkage. Free for non-commercial. | Open |

## Institutional / paid sources

| Source | API | Notes | Status |
|---|---|---|---|
| **Scopus (Elsevier)** | <https://dev.elsevier.com/sc_apis.html> | Most-requested commercial source. Requires institutional key. | Open |
| **Web of Science** | <https://developer.clarivate.com/apis/wos> | Citation-network gold standard. Institutional access. | Open |

## Non-adapter starter tasks

- **PRISMA flow diagram export** — generate a printable PNG/SVG of the included/excluded record counts from the methodology log.
- **Locale-aware date parsing** in `app/services/cleaning.py` — currently assumes ISO; some adapters emit `DD-MM-YYYY`.
- **Add a `--dry-run` flag** to the search CLI for cost-estimation before a full fetch.
- **Improve the empty-state copy** in the frontend project dashboard (`bibmeded/frontend/app/projects/`).
- **Translate the UI** — add an `i18n` scaffold and a Turkish or Spanish locale (high demand from non-English-speaking medical educators).

## Claiming and shipping

1. Comment on (or open) an issue for the item you want.
2. Fork → branch off `master` → implement → `pytest -q`.
3. Open a PR using the template. Tag the issue with `Closes #N`.
4. Expect review within a week. PRs that include tests get merged faster.
