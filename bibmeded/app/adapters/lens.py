import inspect

import httpx

from app.adapters.base import BaseSourceAdapter, RawAuthor, RawRecord, SearchResponse


LENS_API = "https://api.lens.org"
_PAGE_SIZE = 200
_MAX_OFFSET_RESULTS = 10_000


def _clean_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _normalize_doi(raw: str | None) -> str | None:
    if not raw:
        return None
    value = str(raw).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.startswith(prefix):
            return value.removeprefix(prefix).strip()
    return value


class LensAdapter(BaseSourceAdapter):
    name = "lens"
    display_name = "Lens.org"
    requires_api_key = True

    def __init__(self, api_key: str = ""):
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)
        self._api_key = api_key

    async def search(self, query: str, **kwargs) -> SearchResponse:
        payload = self._build_payload(query, kwargs, from_=0, size=_PAGE_SIZE)
        data = await self._post(payload)
        records = self._data_records(data)
        ids = [
            record_id
            for record_id in (self._extract_id(record) for record in records)
            if record_id
        ]
        total = self._extract_total(data)
        return SearchResponse(total_count=total, ids=ids)

    async def search_paginated(self, query: str, **kwargs):
        offset = 0
        while True:
            payload = self._build_payload(query, kwargs, from_=offset, size=_PAGE_SIZE)
            data = await self._post(payload)
            records = self._data_records(data)
            if not records:
                break
            ids = [
                record_id
                for record_id in (self._extract_id(record) for record in records)
                if record_id
            ]
            if ids:
                yield ids
            offset += len(records)
            total = self._extract_total(data)
            if offset >= _MAX_OFFSET_RESULTS or (total and offset >= total):
                break

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
                if self._extract_id(record):
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
        return _clean_string(item.get("lens_id"))

    @staticmethod
    def _data_records(payload: dict) -> list[dict]:
        records = payload.get("data")
        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
        return []

    @staticmethod
    def _extract_total(payload: dict) -> int:
        try:
            return max(int(payload.get("total", 0) or 0), 0)
        except (TypeError, ValueError):
            return 0

    async def _post(self, payload: dict) -> dict:
        resp = await self._client.post(f"{LENS_API}/scholarly/search", json=payload)
        # Lens uses 404 for valid searches with no matching records. The URL is
        # fixed here and this adapter does not use scroll IDs, so that response
        # unambiguously represents an empty result set for this request.
        if resp.status_code == httpx.codes.NOT_FOUND:
            return {"total": 0, "data": []}
        resp.raise_for_status()
        parsed = await self._parse_json(resp)
        if not isinstance(parsed, dict):
            raise ValueError("Lens API returned an invalid response")
        return parsed

    @staticmethod
    async def _parse_json(resp: httpx.Response) -> object:
        result = resp.json()
        if inspect.isawaitable(result):
            result = await result
        return result

    def _to_raw(self, record: dict) -> RawRecord:
        external_ids = {"lens_id": self._extract_id(record)}
        doi: str | None = None
        for external_id in record.get("external_ids") or []:
            if not isinstance(external_id, dict):
                continue
            id_type = str(external_id.get("type") or "").strip().lower()
            value = external_id.get("value")
            if not id_type or value is None:
                continue
            if id_type == "doi":
                normalized = _normalize_doi(str(value))
                if normalized:
                    external_ids["doi"] = normalized
                    doi = normalized
            elif id_type in {"pmid", "pmcid", "coreid", "openalex", "magid"}:
                normalized = str(value).strip()
                if normalized:
                    external_ids[id_type] = normalized

        source = record.get("source") or {}
        if not isinstance(source, dict):
            source = {}
        issn = source.get("issn") or []
        if isinstance(issn, list) and issn and isinstance(issn[0], dict):
            journal_issn = _clean_string(issn[0].get("value")) or None
        else:
            journal_issn = None

        authors: list[RawAuthor] = []
        for author in record.get("authors") or []:
            if not isinstance(author, dict):
                continue
            first = _clean_string(author.get("first_name"))
            last = _clean_string(author.get("last_name"))
            name = f"{first} {last}".strip() or _clean_string(author.get("display_name"))
            if not name:
                continue
            orcid = None
            for author_id in author.get("ids") or []:
                if isinstance(author_id, dict) and author_id.get("type") == "orcid":
                    orcid = (
                        _clean_string(author_id.get("value"))
                        .replace("https://orcid.org/", "")
                        .replace("http://orcid.org/", "")
                    ) or None
            affiliations = author.get("affiliations") or []
            affiliation = (
                _clean_string(affiliations[0].get("name")) or None
                if affiliations and isinstance(affiliations[0], dict)
                else None
            )
            authors.append(RawAuthor(name=name, orcid=orcid, affiliation=affiliation))

        mesh_terms = [
            mesh.get("mesh_heading")
            for mesh in (record.get("mesh_terms") or [])
            if isinstance(mesh, dict) and isinstance(mesh.get("mesh_heading"), str)
        ]
        mesh_terms = [m for m in mesh_terms if m]

        references: list[str] = []
        for ref in record.get("references") or []:
            if isinstance(ref, dict):
                ref_id = ref.get("lens_id")
                if ref_id:
                    references.append(str(ref_id))

        keywords = record.get("keywords")

        return RawRecord(
            source_id=external_ids["lens_id"],
            source_database="lens",
            title=_clean_string(record.get("title")),
            abstract=_optional_string(record.get("abstract")),
            doi=doi,
            year=self._extract_year(record),
            journal_name=_clean_string(source.get("title")) or None,
            journal_issn=journal_issn,
            publication_type=_clean_string(record.get("publication_type")) or None,
            authors=authors,
            mesh_terms=mesh_terms or [],
            keywords=[k for k in keywords if isinstance(k, str)] if isinstance(keywords, list) else [],
            references=references,
            external_ids=external_ids,
        )

    @staticmethod
    def _extract_year(record: dict) -> int | None:
        year = record.get("year_published")
        if isinstance(year, int) and not isinstance(year, bool):
            return year
        published = record.get("date_published_parts")
        if isinstance(published, list) and published:
            try:
                return int(published[0])
            except (TypeError, ValueError):
                pass
        published_date = record.get("date_published")
        if isinstance(published_date, str) and len(published_date) >= 4:
            try:
                return int(published_date[:4])
            except ValueError:
                pass
        return None

    async def close(self) -> None:
        await self._client.aclose()

    def methodology_label(self) -> str:
        return "Lens.org Scholarly API"
