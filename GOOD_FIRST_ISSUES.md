# Good First Contributions

> **October contribution sprint:** Hacktoberfest 2026 no longer counts pull requests, so this is not a swag or PR-count event. We are still running an October sprint: every issue labelled [`hacktoberfest`](https://github.com/ata381/BibMedEd/issues?q=is%3Aissue+is%3Aopen+label%3Ahacktoberfest) is scoped, has acceptance criteria, and can be tested without live APIs. Maintainers aim to review sprint PRs within three working days, and contributors are credited in the CHANGELOG and release notes.

The fastest way to make a high-impact contribution to BibMedEd is to write an adapter. The adapter module is usually focused, while a complete contribution also includes captured API fixtures, parsing and pagination tests, and short source-specific documentation.

How to claim:

1. Pick an item below.
2. Comment on its existing GitHub issue and ask to be assigned.
3. If no issue exists, open an [adapter request](https://github.com/ata381/BibMedEd/issues/new?template=adapter_request.yml) and tick the claim checkbox.
4. Open a PR linked to the issue and include fixture-based tests.

Open items have one active owner at a time. Maintainers aim to acknowledge claims within three working days; if a claim has no update for two weeks, it may be opened for someone else.

Read the [adapter guide](https://ata381.github.io/BibMedEd/adapters/) first. Reference implementations: `bibmeded/bibmeded/adapters/pubmed.py`, `openalex.py`, `crossref.py`, `semantic_scholar.py`, and the API-keyed `lens.py`.

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
| **Dimensions** | <https://docs.dimensions.ai/dsl/> | Strong grant + clinical-trial linkage. Free for non-commercial. | [#69](https://github.com/ata381/BibMedEd/issues/69) |

## Institutional / paid sources

| Source | API | Notes | Status |
|---|---|---|---|
| **Scopus (Elsevier)** | <https://dev.elsevier.com/sc_apis.html> | Most-requested commercial source. Requires institutional key. | Open |
| **Web of Science** | <https://developer.clarivate.com/apis/wos> | Citation-network gold standard. Institutional access. | Open |

## Non-adapter starter tasks

- **i18n scaffold + Turkish locale** — [#16](https://github.com/ata381/BibMedEd/issues/16)
- **BibTeX export** — [#60](https://github.com/ata381/BibMedEd/issues/60)
- **Robust country extraction from affiliations** — [#63](https://github.com/ata381/BibMedEd/issues/63)
- **CAGR and doubling time in publication trends** — [#62](https://github.com/ata381/BibMedEd/issues/62)
- **Lotka's law for author productivity** — [#61](https://github.com/ata381/BibMedEd/issues/61)
- **Web of Science plain-text export for VOSviewer / Bibliometrix** — [#68](https://github.com/ata381/BibMedEd/issues/68)
- **Troubleshooting / FAQ docs page** — [#67](https://github.com/ata381/BibMedEd/issues/67)
- **Example Jupyter notebook for the REST API** — [#66](https://github.com/ata381/BibMedEd/issues/66)
- **Table-driven required-key configuration for adapters** — [#88](https://github.com/ata381/BibMedEd/issues/88)
- **PRISMA 2020 title/abstract vs full-text screening stages** — [#91](https://github.com/ata381/BibMedEd/issues/91)
- **Strategic diagram (thematic quadrants)** — [#92](https://github.com/ata381/BibMedEd/issues/92)
- **Accessible ConfirmDialog replacing native `confirm()`** — [#90](https://github.com/ata381/BibMedEd/issues/90)
- **Extend axe accessibility scans to dashboard tabs and read-only mode** — [#89](https://github.com/ata381/BibMedEd/issues/89)
- **Contract check that e2e API mocks match real backend response shapes** — [#78](https://github.com/ata381/BibMedEd/issues/78)
- **Fix SAWarning "nested transaction already deassociated" in the persist loop** — [#87](https://github.com/ata381/BibMedEd/issues/87)
- **Stored search query in the sample project** — [#94](https://github.com/ata381/BibMedEd/issues/94)
- **Prevent node-label overlap in the network graph** — [#95](https://github.com/ata381/BibMedEd/issues/95)
- **Break the `main` and `routers.search` import cycle** — [#98](https://github.com/ata381/BibMedEd/issues/98)
- **Locale-aware date parsing** in `bibmeded/services/cleaning.py`: currently assumes ISO; some adapters emit `DD-MM-YYYY`.

For an untracked idea above, open a [feature request](https://github.com/ata381/BibMedEd/issues/new?template=feature_request.yml) before starting so the scope can be agreed.

## Claiming and shipping

1. Comment on (or open) an issue for the item you want.
2. Fork → branch off `master` → implement → `pytest -q`.
3. Open a PR using the template. Tag the issue with `Closes #N`.
4. Expect review within a week. PRs that include tests get merged faster.
