"""Semantic Scholar Graph API v1 adapter.

Free tier: ~100 requests / 5 minutes per IP, no key required. Pass an API key to
the constructor for the keyed tier (1 req/sec). Search offset is capped at 9999
by the upstream API; this adapter stops pagination there and reports that the
search was capped via the upstream `total` count returned by `search()`.

Docs: https://api.semanticscholar.org/api-docs/graph
"""

import inspect
from collections.abc import AsyncGenerator

import httpx

from app.adapters.base import BaseSourceAdapter, RawAuthor, RawRecord, SearchResponse


S2_API = "https://api.semanticscholar.org/graph/v1"
_SEARCH_FIELDS = "paperId,externalIds,title"
_DETAIL_FIELDS = (
    "paperId,externalIds,title,abstract,year,publicationTypes,"
    "authors.name,authors.externalIds,"
    "journal,publicationVenue,fieldsOfStudy,"
    "references.externalIds"
)
_S2_MAX_OFFSET = 9999  # upstream caps offset at 9999 inclusive — 9999 is still a valid offset
_PAGE_SIZE = 100
_BATCH_LIMIT = 500  # /paper/batch accepts at most 500 IDs per call


class SemanticScholarAdapter(BaseSourceAdapter):
    name = "semanticscholar"
    display_name = "Semantic Scholar"
    requires_api_key = False  # free tier is open; API key only raises the rate limit

    def __init__(self, api_key: str = ""):
        headers = {"x-api-key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)
        self._api_key = api_key

    @staticmethod
    async def _parse_json(resp) -> dict:
        result = resp.json()
        if inspect.isawaitable(result):
            result = await result
        return result

    def _build_year_filter(self, **kwargs) -> str | None:
        start = kwargs.get("year_start")
        end = kwargs.get("year_end")
        if start and end:
            return f"{start}-{end}"
        if start:
            return f"{start}-"
        if end:
            return f"-{end}"
        return None

    async def search(self, query: str, **kwargs) -> SearchResponse:
        params: dict = {"query": query, "limit": _PAGE_SIZE, "fields": _SEARCH_FIELDS}
        year_filter = self._build_year_filter(**kwargs)
        if year_filter:
            params["year"] = year_filter
        resp = await self._client.get(f"{S2_API}/paper/search", params=params)
        resp.raise_for_status()
        data = await self._parse_json(resp)
        total = int(data.get("total", 0))
        ids = [p["paperId"] for p in data.get("data", []) if p.get("paperId")]
        return SearchResponse(total_count=total, ids=ids)

    async def search_paginated(self, query: str, **kwargs) -> AsyncGenerator[list[str], None]:
        offset = 0
        while True:
            params: dict = {
                "query": query,
                "limit": _PAGE_SIZE,
                "offset": offset,
                "fields": _SEARCH_FIELDS,
            }
            year_filter = self._build_year_filter(**kwargs)
            if year_filter:
                params["year"] = year_filter
            resp = await self._client.get(f"{S2_API}/paper/search", params=params)
            resp.raise_for_status()
            data = await self._parse_json(resp)
            ids = [p["paperId"] for p in data.get("data", []) if p.get("paperId")]
            if not ids:
                break
            yield ids
            next_offset = data.get("next")
            # Offset cap is INCLUSIVE — 9999 is still a valid offset to fetch.
            # Stop only when the server says there is no more data, or when the next
            # offset would exceed the documented cap.
            if next_offset is None or next_offset > _S2_MAX_OFFSET:
                break
            offset = int(next_offset)

    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        if not ids:
            return []
        records: list[RawRecord] = []
        # S2 /paper/batch caps at 500 IDs per call — chunk so direct callers can
        # pass arbitrary-size lists without triggering a 400.
        for start in range(0, len(ids), _BATCH_LIMIT):
            chunk = ids[start : start + _BATCH_LIMIT]
            resp = await self._client.post(
                f"{S2_API}/paper/batch",
                params={"fields": _DETAIL_FIELDS},
                json={"ids": chunk},
            )
            resp.raise_for_status()
            data = await self._parse_json(resp)
            # The batch endpoint returns a list; entries are None for ids that couldn't be resolved.
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                records.append(self._to_raw(item))
        return records

    def _to_raw(self, item: dict) -> RawRecord:
        external_ids_raw = item.get("externalIds") or {}
        # S2 returns DOIs in mixed case; cross-source dedup keys on lowercase DOI.
        doi_raw = external_ids_raw.get("DOI")
        doi = doi_raw.lower() if doi_raw else None

        external_ids: dict[str, str] = {}
        if doi:
            external_ids["doi"] = doi
        if external_ids_raw.get("PubMed"):
            external_ids["pmid"] = str(external_ids_raw["PubMed"])
        if item.get("paperId"):
            external_ids["semantic_scholar"] = str(item["paperId"])

        # Journal metadata can live in `journal` (free-text shape) or `publicationVenue`
        # (canonical-venue shape) depending on the paper.
        journal = item.get("journal") or {}
        venue = item.get("publicationVenue") or {}
        journal_name = journal.get("name") or venue.get("name")
        journal_issn = None
        if isinstance(venue.get("issn"), str):
            journal_issn = venue["issn"]

        publication_type = None
        types = item.get("publicationTypes") or []
        if types:
            publication_type = types[0]

        authors: list[RawAuthor] = []
        for a in item.get("authors", []) or []:
            name = (a.get("name") or "").strip()
            if not name:
                continue
            author_ext = a.get("externalIds") or {}
            orcid_raw = author_ext.get("ORCID")
            orcid = (
                orcid_raw.replace("https://orcid.org/", "").replace("http://orcid.org/", "")
                if orcid_raw
                else None
            )
            authors.append(RawAuthor(name=name, orcid=orcid, affiliation=None))

        # References — lowercase DOIs when available; skip refs without identifiers.
        references: list[str] = []
        for ref in item.get("references") or []:
            ref_ids = (ref or {}).get("externalIds") or {}
            if ref_ids.get("DOI"):
                references.append(str(ref_ids["DOI"]).lower())

        keywords = [s for s in (item.get("fieldsOfStudy") or []) if s]

        return RawRecord(
            source_id=str(item.get("paperId") or doi or ""),
            source_database="semanticscholar",
            title=item.get("title") or "",
            abstract=item.get("abstract"),
            doi=doi,
            year=item.get("year"),
            journal_name=journal_name,
            journal_issn=journal_issn,
            publication_type=publication_type,
            authors=authors,
            mesh_terms=[],
            keywords=keywords,
            references=references,
            external_ids=external_ids,
        )

    def methodology_label(self) -> str:
        return "Semantic Scholar Graph API"

    async def close(self) -> None:
        await self._client.aclose()
