# Writing Adapters

BibMedEd uses a plug-and-play adapter pattern. Each data source (PubMed, OpenAlex, Scopus, IEEE, etc.) is a single Python file that implements the `BaseSourceAdapter` interface. Adding a new source requires no changes to the core application.

## The Contract

Every adapter must implement two methods and declare three class attributes:

```python
from app.adapters.base import BaseSourceAdapter, RawRecord, SearchResponse

class MyAdapter(BaseSourceAdapter):
    name = "mysource"              # unique identifier
    display_name = "My Source"     # shown in the UI
    requires_api_key = False       # if True, UI shows "(API key)" badge

    async def search(self, query: str, **kwargs) -> SearchResponse:
        """Search the source, return total count and a list of record IDs."""
        ...

    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        """Fetch full records by ID, return as RawRecords."""
        ...
```

Drop the file into `app/adapters/` and restart the worker. The registry auto-discovers it.

## RawRecord Reference

Every adapter maps its source data into `RawRecord` — the universal format that the rest of the pipeline understands:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | `str` | Yes | The source's native ID (e.g., PMID, OpenAlex ID) |
| `source_database` | `str` | Yes | Adapter name (e.g., `"pubmed"`, `"openalex"`) |
| `title` | `str` | Yes | Paper title |
| `abstract` | `str \| None` | No | Abstract text |
| `doi` | `str \| None` | No | DOI without URL prefix |
| `year` | `int \| None` | No | Publication year |
| `journal_name` | `str \| None` | No | Journal display name |
| `journal_issn` | `str \| None` | No | ISSN |
| `publication_type` | `str \| None` | No | e.g., "article", "review" |
| `authors` | `list[RawAuthor]` | No | Author list with name, orcid, affiliation |
| `mesh_terms` | `list[str]` | No | MeSH terms (PubMed-specific, empty for other sources) |
| `keywords` | `list[str]` | No | Author keywords |
| `references` | `list[str]` | No | IDs of referenced works |
| `external_ids` | `dict[str, str]` | No | Cross-database IDs for deduplication |

### `external_ids` Convention

This is how cross-database deduplication works. Populate every ID you know about:

```python
external_ids = {
    "openalex": "W123456",
    "pmid": "32064006",
    "doi": "10.1016/j.example.2024.01.001",
}
```

The dedup engine matches on DOI first, then PMID. The more IDs you provide, the better dedup works.

## Optional Overrides

For sources with cursor-based pagination or large datasets, override these defaults:

### `search_paginated()`

By default, yields all IDs from a single `search()` call. Override for cursor-based APIs:

```python
async def search_paginated(self, query: str, **kwargs) -> AsyncGenerator[list[str], None]:
    cursor = "*"
    while cursor:
        resp = await self._client.get("/works", params={"search": query, "cursor": cursor})
        data = resp.json()
        yield [r["id"] for r in data["results"]]
        cursor = data.get("next_cursor")
```

### `fetch_stream()`

By default, slices IDs into batches of 200 and calls `fetch()` per batch. Override if your API has native batch/streaming support.

### `methodology_label()`

Returns `"{display_name} API"` by default. Override for a more descriptive label in the methodology log:

```python
def methodology_label(self) -> str:
    return "PubMed E-Utilities"
```

## Walkthrough: OpenAlex Adapter

The shipped OpenAlex adapter (`app/adapters/openalex.py`) is a complete real-world example. Key patterns:

1. **`search()`** hits `/works?search=...` and returns the first page of IDs + total count
2. **`search_paginated()`** overrides the default to use OpenAlex cursor pagination
3. **`fetch()`** uses pipe-separated filters to batch-fetch records
4. **`_to_raw()`** maps OpenAlex JSON to `RawRecord`, including:
   - Extracting cross-database IDs from the `ids` object
   - Reconstructing abstracts from OpenAlex's inverted index format
   - Parsing author affiliations from nested institution objects

Read the full source: [`app/adapters/openalex.py`](https://github.com/ata381/Tip-egitimi-entegrasyon/blob/master/bibmeded/app/adapters/openalex.py)

## Step-by-Step: Adding a New Source

1. Create `app/adapters/mysource.py`
2. Implement `search()` and `fetch()` mapping to `RawRecord`
3. Populate `external_ids` with every cross-reference ID the API provides
4. Restart the worker: `docker compose restart worker`
5. The new source appears in the search page dropdown automatically
