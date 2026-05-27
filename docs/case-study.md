# Case Study: AI in Undergraduate Medical Education (2014–2024)

> A worked example showing how a medical-education researcher uses BibMedEd to go from a research question to a deduplicated dataset, six analyses, two network visualisations, and a PRISMA-ready methodology log in under thirty minutes.

This case study uses a real research question — *"How has AI been integrated into undergraduate medical-education curricula over the last decade?"* — and walks through every step you would actually run. Screenshots correspond to the UI shown on the [home page tour](index.md#user-interface-tour).

## 1. Frame the research question

Reviews live or die on the question's PICO-style structure. For a bibliometric scope (rather than effectiveness synthesis), we relax PICO into a search-friendly form:

| Element | Value |
|---|---|
| Population | Undergraduate medical students / curricula |
| Concept | Artificial intelligence, machine learning, large language models |
| Context | Education, curriculum, training |
| Timeframe | 2014–2024 (last decade) |
| Languages | English (recall pre-filter) |

This becomes our query string:

```
("artificial intelligence" OR "machine learning" OR "large language models")
AND ("medical education" OR "medical curriculum" OR "medical students")
AND education[Filter]
```

## 2. Create the project

In BibMedEd's UI, **New project → name it "AI in UME 2014-2024"**. Pick the data sources for this run — for an OA-leaning sweep we'd choose **PubMed + OpenAlex** (both ship by default; CrossRef and Europe PMC are [open contribution issues](https://github.com/ata381/BibMedEd/issues?q=is%3Aissue+is%3Aopen+label%3Aadapter) if you want broader coverage).

Pasted into the search box, the query runs concurrently against both sources via Celery workers. The progress bar on the search page shows live record counts as each source streams in.

What's happening under the hood:
- Each adapter's `search()` returns total counts and IDs.
- Each adapter's `fetch()` pages the records and maps them to a unified `RawRecord` dataclass.
- Every step is recorded into the methodology log with a timestamp.

For this query: PubMed returns ~3,200 hits, OpenAlex ~5,800. Cross-source dedup runs automatically.

## 3. Dedup and inspect

Cross-source dedup keys on `external_ids.doi` and `external_ids.pmid` — both normalised (lower-case DOI with `https://doi.org/` prefix stripped, whitespace-trimmed PMID). For this query the dedup pass removes ~2,400 records (mostly OpenAlex records that already have a PMID and matched a PubMed hit).

Final dataset: ~6,600 unique publications. The results table is sortable by year, citation count, journal, and source. Click any row for the full abstract and identifiers.

> **Tip:** the default result cap is 2,000; bump it via `BIBMEDED_MAX_RECORDS` in `.env` for larger sweeps. The progress bar respects the cap and tells you what's truncated.

## 4. Screen by citation threshold (optional)

For a scoping-style bibliometric review where citation impact matters, you can bulk-exclude papers below a citation threshold from the results page. BibMedEd records the threshold and the count removed into the methodology log — you don't have to remember the magic number when writing Methods.

For this case study we leave everything in.

## 5. Run the six analyses

From the project dashboard, click **Run all analyses**. BibMedEd executes:

1. **Publications over time** — yearly counts, growth rates, cumulative curve. Expectation for this query: explosive growth post-2022 (ChatGPT release).
2. **Author productivity** — top authors by publication count and h-index proxy (citation-weighted ranking on this subset).
3. **Country distribution** — affiliations parsed with case-insensitive country extraction (the [analysis cleaning service](https://github.com/ata381/BibMedEd/blob/master/bibmeded/app/services/cleaning.py) handles variants like "USA" vs "United States" vs "U.S.").
4. **Keyword co-occurrence** — MeSH terms and author keywords, case-normalised so "AI" and "ai" don't double-count. D3 network of the top-30.
5. **Citation impact** — distribution of citation counts, highly-cited papers list, journal-weighted impact.
6. **Journal ranking** — publication counts, normalised by quartile if available.

Each analysis is rendered as a chart + table on the dashboard. Click into any node on the D3 networks to filter the underlying table.

## 6. Export

From the **Export** page:

- **.RIS** — feeds straight into Zotero, EndNote, or Mendeley.
- **.CSV** — for ad-hoc analysis in pandas, R, or Excel.
- **Methodology log** — a plain-text file like the sample below. Cite it as supplementary material in your PRISMA Methods section.

```
BibMedEd methodology log — Project: AI in UME 2014-2024
Generated: 2026-05-27T14:22:11Z
DOI of software: 10.5281/zenodo.20404321

Step  Time            Action                          Details
1     2026-05-27 14:05  search.start                  query="(artificial intelligence...) AND (medical education...)", sources=[pubmed, openalex], date_from=2014-01-01, date_to=2024-12-31
2     2026-05-27 14:05  adapter.pubmed.search         total=3204, batch_size=200
3     2026-05-27 14:07  adapter.pubmed.fetch.complete records=3204, errors=0
4     2026-05-27 14:05  adapter.openalex.search       total=5821, batch_size=200
5     2026-05-27 14:08  adapter.openalex.fetch.complete records=5821, errors=0
6     2026-05-27 14:09  dedup.cross_source            input=9025, output=6612, removed_by_doi=1980, removed_by_pmid=433
7     2026-05-27 14:09  analysis.publications.run     yearly_counts=[...], total=6612, growth_rate_2022_2023=187.4
8     2026-05-27 14:10  analysis.authors.run          unique=18421, top_5=[...]
... (one line per step, no manual transcription required)
```

This file is the part most researchers find surprisingly useful. [PRISMA 2020](https://doi.org/10.1136/bmj.n71) items 7 (search strategy) and 9 (deduplication process) are answered by lines you don't have to write yourself.

## 7. Write up

Cite BibMedEd in your paper's Methods section:

> Bibliometric data were retrieved via BibMedEd (v0.1.2; Akillioglu, 2026; doi:10.5281/zenodo.20404322), an open-source platform that performs multi-source bibliographic search, automated cross-source deduplication via DOI and PMID, and bibliometric analysis. The full pipeline — search query, source order, retrieval timestamps, deduplication counts, and exclusion filters — is recorded in the BibMedEd methodology log supplied as Supplementary File S1.

That's it. Search to write-up in under thirty minutes, every step reproducible because every step is logged.

## Reproducing this case study

Once you have the stack running ([deploy guide](deploy.md)):

1. New project: *AI in UME 2014-2024*.
2. Source: PubMed + OpenAlex.
3. Query (paste in full):
   ```
   ("artificial intelligence" OR "machine learning" OR "large language models")
   AND ("medical education" OR "medical curriculum" OR "medical students")
   AND education[Filter]
   ```
4. Date range: 2014-01-01 to 2024-12-31.
5. Run all analyses; export methodology log.

Your numbers will differ from this case study (PubMed and OpenAlex are live and growing) — that's the point. The query and the methodology log are what you cite, not the snapshot.

## Want a different worked example?

If you've run a bibliometric study with BibMedEd, a one-page case-study contribution is one of the highest-leverage PRs you can send. See [CONTRIBUTING.md](https://github.com/ata381/BibMedEd/blob/master/CONTRIBUTING.md) — "Improve docs and examples". Real-world studies double as marketing and as tutorial material; they will be linked from this page.
