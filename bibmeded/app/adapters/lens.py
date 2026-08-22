import inspect

import httpx

from app.adapters.base import BaseSourceAdapter, RawAuthor, RawRecord, SearchResponse


LENS_API = "https://api.lens.org"
_PAGE_SIZE = 200


def _normalize_doi(raw: str | None) -> str | None:
    if not raw:
        return None
    return str(raw).replace("https://doi.org/", "").replace("http://doi.org/", "").lower()


class LensAdapter(BaseSourceAdapter):
    name = "lens"
    display_name = "Lens.org"
    requires_api_key = True

    def __init__(self, api_key: str = ""):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def search(self, query: str, **kwargs) -> SearchResponse:
        payload = self._build_payload(query, kwargs, from_=0, size=_PAGE_SIZE)
        data = await self._post(payload)
        records = self._data_records(data)
        ids = [self._extract_id(record) for record in records]
        total = int(data.get("total", 0) or 0)
        return SearchResponse(total_count=total, ids=ids)

    async def search_paginated(self, query: str, **kwargs):
        offset = 0
        while True:
            payload = self._build_payload(query, kwargs, from_=offset, size=_PAGE_SIZE)
            data = await self._post(payload)
            records = self._data_records(data)
            ids = [self._extract_id(record) for record in records]
            if not ids:
                break
            yield ids
            if len(records) < _PAGE_SIZE:
                break
            offset += len(records)

    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        if not ids:
            return []
        records: list[RawRecord] = []
        for start in range(0, len(ids), _PAGE_SIZE):
            batch = ids[start : start + _PAGE_SIZE]
            payload = {
                "query": {
                    "terms": {
                        "lens_id": batch
                    }
                },
                "size": len(batch),
                "include": [
                    "authors",
                    "title",
                    "year_published",
                    "date_published",
                    "publication_type",
                    "source",
                    "keywords",
                    "mesh_terms",
                    "abstract",
                    "external_ids",
                    "references",
                    "lens_id",
                ],
            }
            data = await self._post(payload)
            for record in self._data_records(data):
                records.append(self._to_raw(record))
        return records

    def _build_payload(self, query: str, kwargs: dict, from_: int, size: int) -> dict:
        year_filter = self._build_year_filter(
            year_start=kwargs.get("year_start"),
            year_end=kwargs.get("year_end"),
        )

        must = [{"query_string": {"query": query, "fields": ["ui_default"], "default_operator": "and"}}]
        if year_filter is not None:
            must.append({"range": {"year_published": year_filter}})

        return {
            "query": {"bool": {"must": must}},
            "from": from_,
            "size": size,
            "include": [
                "lens_id",
                "title",
                "year_published",
                "date_published",
                "publication_type",
                "source",
                "keywords",
                "mesh_terms",
                "abstract",
                "external_ids",
                "authors",
                "references",
            ],
        }

    @staticmethod
    def _build_year_filter(*, year_start: str | None = None, year_end: str | None = None) -> dict | None:
        if not year_start and not year_end:
            return None
        constraints: dict[str, str] = {}
        if year_start:
            constraints["gte"] = str(year_start)
        if year_end:
            constraints["lte"] = str(year_end)
        return constraints

    @staticmethod
    def _extract_id(item: dict | None) -> str:
        if not isinstance(item, dict):
            return ""
        return item.get("lens_id", "") or ""

    @staticmethod
    def _data_records(payload: dict) -> list[dict]:
        records = payload.get("data")
        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
        return []

    async def _post(self, payload: dict) -> dict:
        resp = await self._client.post(f"{LENS_API}/scholarly/search", json=payload)
        resp.raise_for_status()
        parsed = await self._parse_json(resp)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    async def _parse_json(resp: httpx.Response) -> dict:
        result = resp.json()
        if inspect.isawaitable(result):
            result = await result
        return result

    def _to_raw(self, record: dict) -> RawRecord:
        external_ids = {"lens_id": str(record.get("lens_id", "") or "").strip()}
        doi: str | None = None
        for external_id in record.get("external_ids") or []:
            if not isinstance(external_id, dict):
                continue
            id_type = external_id.get("type")
            value = external_id.get("value")
            if not id_type or value is None:
                continue
            if id_type == "doi":
                normalized = _normalize_doi(str(value))
                if normalized:
                    external_ids["doi"] = normalized
                    doi = normalized
            elif id_type == "pmid":
                external_ids["pmid"] = str(value)
            elif id_type == "pmcid":
                external_ids["pmcid"] = str(value)
            elif id_type == "coreid":
                external_ids["coreid"] = str(value)

        source = record.get("source") or {}
        issn = source.get("issn") or []
        if isinstance(issn, list) and issn and isinstance(issn[0], dict):
            journal_issn = issn[0].get("value")
        else:
            journal_issn = None

        authors: list[RawAuthor] = []
        for author in record.get("authors") or []:
            if not isinstance(author, dict):
                continue
            first = (author.get("first_name") or "").strip()
            last = (author.get("last_name") or "").strip()
            name = f"{first} {last}".strip()
            if not name:
                continue
            orcid = None
            for author_id in author.get("ids") or []:
                if isinstance(author_id, dict) and author_id.get("type") == "orcid":
                    orcid = str(author_id.get("value", "")).replace("https://orcid.org/", "")
            affiliations = author.get("affiliations") or []
            affiliation = (
                affiliations[0].get("name")
                if affiliations and isinstance(affiliations[0], dict)
                else None
            )
            authors.append(RawAuthor(name=name, orcid=orcid, affiliation=affiliation))

        mesh_terms = [
            mesh.get("mesh_heading")
            for mesh in (record.get("mesh_terms") or [])
            if isinstance(mesh, dict)
        ]
        mesh_terms = [m for m in mesh_terms if m]

        references: list[str] = []
        for ref in record.get("references") or []:
            if isinstance(ref, dict):
                ref_id = ref.get("lens_id")
                if ref_id:
                    references.append(str(ref_id))

        return RawRecord(
            source_id=external_ids.get("lens_id") or str(record.get("lens_id") or ""),
            source_database="lens",
            title=record.get("title") or "",
            abstract=record.get("abstract"),
            doi=doi,
            year=self._extract_year(record),
            journal_name=source.get("title"),
            journal_issn=journal_issn,
            publication_type=record.get("publication_type"),
            authors=authors,
            mesh_terms=mesh_terms or [],
            keywords=[k for k in (record.get("keywords") or []) if isinstance(k, str)],
            references=references,
            external_ids=external_ids,
        )

    @staticmethod
    def _extract_year(record: dict) -> int | None:
        year = record.get("year_published")
        if isinstance(year, int):
            return year
        published = record.get("date_published_parts")
        if isinstance(published, list) and published:
            try:
                return int(published[0])
            except (TypeError, ValueError):
                return None
        return None

    async def close(self) -> None:
        await self._client.aclose()

    def methodology_label(self) -> str:
        return "Lens.org Scholarly API"
