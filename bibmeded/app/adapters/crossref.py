import inspect

import httpx

from app.adapters.base import BaseSourceAdapter, RawAuthor, RawRecord, SearchResponse
from collections.abc import AsyncGenerator

CROSSREF_API = "https://api.crossref.org"


class CrossrefAdapter(BaseSourceAdapter):
    name = "crossref"
    display_name = "CrossRef"
    requires_api_key = False  # polite-pool email is recommended, not required

    def __init__(self, email: str = ""):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._email = email

    def _with_mailto(self, params: dict) -> dict:
        if self._email:
            params = {**params, "mailto": self._email}
        return params

    def _build_filter(self, **kwargs) -> str | None:
        parts = []
        if kwargs.get("year_start"):
            parts.append(f"from-pub-date:{kwargs['year_start']}-01-01")
        if kwargs.get("year_end"):
            parts.append(f"until-pub-date:{kwargs['year_end']}-12-31")
        return ",".join(parts) if parts else None

    @staticmethod
    async def _parse_json(resp) -> dict:
        result = resp.json()
        if inspect.isawaitable(result):
            result = await result
        return result

    async def search(self, query: str, **kwargs) -> SearchResponse:
        params = self._with_mailto({"query": query, "rows": 200})
        date_filter = self._build_filter(**kwargs)
        if date_filter:
            params["filter"] = date_filter
        resp = await self._client.get(f"{CROSSREF_API}/works", params=params)
        resp.raise_for_status()
        data = await self._parse_json(resp)
        msg = data.get("message", {})
        total = msg.get("total-results", 0)
        ids = [item["DOI"] for item in msg.get("items", []) if item.get("DOI")]
        return SearchResponse(total_count=total, ids=ids)

    async def search_paginated(self, query: str, **kwargs) -> AsyncGenerator[list[str], None]:
        cursor: str | None = "*"
        while cursor:
            params = self._with_mailto({"query": query, "rows": 200, "cursor": cursor})
            date_filter = self._build_filter(**kwargs)
            if date_filter:
                params["filter"] = date_filter
            resp = await self._client.get(f"{CROSSREF_API}/works", params=params)
            resp.raise_for_status()
            data = await self._parse_json(resp)
            msg = data.get("message", {})
            ids = [item["DOI"] for item in msg.get("items", []) if item.get("DOI")]
            if not ids:
                break
            yield ids
            cursor = msg.get("next-cursor")

    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        records: list[RawRecord] = []
        for doi in ids:
            try:
                resp = await self._client.get(
                    f"{CROSSREF_API}/works/{doi}",
                    params=self._with_mailto({}),
                )
                resp.raise_for_status()
                data = await self._parse_json(resp)
            except httpx.HTTPError:
                continue
            item = data.get("message")
            if item:
                records.append(self._to_raw(item))
        return records

    def _to_raw(self, item: dict) -> RawRecord:
        doi_raw = item.get("DOI", "") or ""
        doi = doi_raw.lower() if doi_raw else None

        title_arr = item.get("title") or []
        title = title_arr[0] if title_arr else ""

        container = item.get("container-title") or []
        journal_name = container[0] if container else None

        issn_arr = item.get("ISSN") or []
        journal_issn = issn_arr[0] if issn_arr else None

        year = self._extract_year(item)

        authors: list[RawAuthor] = []
        for a in item.get("author", []):
            name = self._compose_name(a)
            if not name:
                continue
            orcid_raw = a.get("ORCID")
            orcid = (
                orcid_raw.replace("https://orcid.org/", "").replace("http://orcid.org/", "")
                if orcid_raw
                else None
            )
            affils = a.get("affiliation") or []
            affiliation = (
                affils[0].get("name")
                if affils and isinstance(affils[0], dict) and affils[0].get("name")
                else None
            )
            authors.append(RawAuthor(name=name, orcid=orcid, affiliation=affiliation))

        keywords = [s for s in (item.get("subject") or []) if s]

        external_ids: dict[str, str] = {}
        if doi:
            external_ids["doi"] = doi

        references = [
            ref["DOI"].lower()
            for ref in (item.get("reference") or [])
            if isinstance(ref, dict) and ref.get("DOI")
        ]

        return RawRecord(
            source_id=doi_raw,
            source_database="crossref",
            title=title,
            abstract=item.get("abstract"),
            doi=doi,
            year=year,
            journal_name=journal_name,
            journal_issn=journal_issn,
            publication_type=item.get("type"),
            authors=authors,
            mesh_terms=[],
            keywords=keywords,
            references=references,
            external_ids=external_ids,
        )

    @staticmethod
    def _extract_year(item: dict) -> int | None:
        for key in ("published-print", "published-online", "issued", "created"):
            block = item.get(key) or {}
            date_parts = block.get("date-parts")
            if date_parts and date_parts[0] and date_parts[0][0] is not None:
                try:
                    return int(date_parts[0][0])
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _compose_name(author: dict) -> str:
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        composed = f"{given} {family}".strip()
        return composed or (author.get("name") or "").strip()

    async def close(self) -> None:
        await self._client.aclose()
