# BibMedEd 0.3: a faster path from first look to reproducible search

BibMedEd 0.3 makes the platform easier to evaluate, easier to automate, and broader in its bibliographic coverage. It also includes the project's first substantial features contributed by developers outside the original maintainer team.

## Explore without configuring an API

A new **Explore sample project** action opens a deterministic synthetic corpus with meaningful author, country, keyword, and citation networks. It makes the full analysis and export workflow available immediately, without an API key or network request.

The sample is clearly labelled and behaves like an ordinary editable project. Delete it and load it again whenever you want to restore the bundled data.

## Run searches from the command line

The new `bibmeded search` command supports two workflows:

```bash
# Estimate the upstream result count without fetching records
bibmeded search "simulation in medical education" --source pubmed --dry-run

# Run a complete search through the same database and Celery pipeline as the UI
bibmeded search "simulation in medical education" \
  --source pubmed \
  --year-start 2020 \
  --year-end 2026 \
  --max-results 500
```

Unknown sources and network failures now produce concise terminal errors instead of Python tracebacks. Full searches require the BibMedEd database and Celery worker to be running.

This workflow was built through community contributions: [@BaygeldiAza](https://github.com/BaygeldiAza) contributed dry-run estimates and full search execution, and [@landon-personal](https://github.com/landon-personal) improved error handling.

## Search Lens.org Scholarly

Lens.org joins PubMed, OpenAlex, CrossRef, and Semantic Scholar as the fifth built-in source. Configure a Lens Scholarly API token with `BIBMEDED_LENS_API_KEY`; the adapter handles pagination, maps scholarly records into BibMedEd's common schema, and participates in the same DOI/PMID deduplication pipeline as every other source.

## Try it or help shape it

- Follow the [quick start](index.md#quick-start) and choose **Explore sample project**.
- Read the [end-to-end case study](case-study.md).
- Share a real workflow or question in [GitHub Discussions](https://github.com/ata381/BibMedEd/discussions).
- Claim a focused task from the [good first contributions list](https://github.com/ata381/BibMedEd/blob/master/GOOD_FIRST_ISSUES.md).

BibMedEd remains a single-tenant, self-hosted tool without built-in authentication. Do not expose a deployment directly to the public internet; review the [security model](deploy.md#security-model) first.
