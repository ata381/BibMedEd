import inspect

import httpx

from bibmeded.adapters.base import BaseSourceAdapter, RawAuthor, RawRecord, SearchResponse
from collections.abc import AsyncGenerator

OPENALEX_API = "https://api.openalex.org"

COUNTRY_NAMES = {
    "US": "USA", "GB": "UK", "CN": "China", "DE": "Germany", "JP": "Japan",
    "CA": "Canada", "AU": "Australia", "FR": "France", "IT": "Italy", "ES": "Spain",
    "KR": "South Korea", "IN": "India", "BR": "Brazil", "NL": "Netherlands", "TR": "Turkey",
    "SE": "Sweden", "CH": "Switzerland", "IR": "Iran", "TW": "Taiwan", "SA": "Saudi Arabia",
    "SG": "Singapore", "BE": "Belgium", "DK": "Denmark", "NO": "Norway", "FI": "Finland",
    "AT": "Austria", "PL": "Poland", "IL": "Israel", "PT": "Portugal", "IE": "Ireland",
    "NZ": "New Zealand", "GR": "Greece", "CZ": "Czech Republic", "TH": "Thailand", "MY": "Malaysia",
    "MX": "Mexico", "EG": "Egypt", "ZA": "South Africa", "PK": "Pakistan", "CO": "Colombia",
    "CL": "Chile", "AR": "Argentina", "ID": "Indonesia", "NG": "Nigeria", "RU": "Russia",
    "RO": "Romania", "HU": "Hungary",
}


def _institution_country(institution: dict) -> str | None:
    code = institution.get("country_code")
    if not isinstance(code, str):
        return None
    code = code.strip().upper()
    if len(code) != 2 or not code.isascii() or not code.isalpha():
        return None
    return COUNTRY_NAMES.get(code, code)


class OpenAlexAdapter(BaseSourceAdapter):
    name = "openalex"
    display_name = "OpenAlex"
    requires_api_key = False

    def __init__(self, email: str = ""):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._email = email

    @staticmethod
    async def _parse_json(resp) -> dict:
        result = resp.json()
        if inspect.isawaitable(result):
            result = await result
        return result

    def _build_filter(self, **kwargs) -> str | None:
        """Build OpenAlex filter string from year_start/year_end kwargs."""
        parts = []
        if kwargs.get("year_start"):
            parts.append(f"from_publication_date:{kwargs['year_start']}-01-01")
        if kwargs.get("year_end"):
            parts.append(f"to_publication_date:{kwargs['year_end']}-12-31")
        return ",".join(parts) if parts else None

    async def search(self, query: str, **kwargs) -> SearchResponse:
        params = {"search": query, "per_page": 200}
        date_filter = self._build_filter(**kwargs)
        if date_filter:
            params["filter"] = date_filter
        if self._email:
            params["mailto"] = self._email
        resp = await self._client.get(f"{OPENALEX_API}/works", params=params)
        resp.raise_for_status()
        data = await self._parse_json(resp)
        total = data["meta"]["count"]
        ids = [self._extract_id(r["id"]) for r in data["results"]]
        return SearchResponse(total_count=total, ids=ids)

    async def search_paginated(self, query: str, **kwargs) -> AsyncGenerator[list[str], None]:
        self.upstream_total = None
        cursor = "*"
        while cursor:
            params = {"search": query, "per_page": 200, "cursor": cursor}
            date_filter = self._build_filter(**kwargs)
            if date_filter:
                params["filter"] = date_filter
            if self._email:
                params["mailto"] = self._email
            resp = await self._client.get(f"{OPENALEX_API}/works", params=params)
            resp.raise_for_status()
            data = await self._parse_json(resp)
            if cursor == "*":
                self.upstream_total = data.get("meta", {}).get("count")
            ids = [self._extract_id(r["id"]) for r in data["results"]]
            if not ids:
                break
            yield ids
            cursor = data.get("next_cursor")

    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        filter_str = "|".join(f"openalex:{oid}" for oid in ids)
        params = {"filter": filter_str, "per_page": 200}
        if self._email:
            params["mailto"] = self._email
        resp = await self._client.get(f"{OPENALEX_API}/works", params=params)
        resp.raise_for_status()
        data = await self._parse_json(resp)
        return [self._to_raw(work) for work in data["results"]]

    def _to_raw(self, work: dict) -> RawRecord:
        raw_ids = work.get("ids", {})
        external_ids: dict[str, str] = {}
        if "openalex" in raw_ids:
            external_ids["openalex"] = self._extract_id(str(raw_ids["openalex"]))
        if "pmid" in raw_ids:
            external_ids["pmid"] = str(raw_ids["pmid"]).split("/")[-1]
        if "doi" in raw_ids:
            doi_str = str(raw_ids["doi"])
            external_ids["doi"] = doi_str.replace("https://doi.org/", "").lower()

        primary_loc = work.get("primary_location") or {}
        source = primary_loc.get("source") or {}

        authors = []
        for authorship in work.get("authorships", []):
            author_info = authorship.get("author", {})
            name = author_info.get("display_name", "")
            orcid_raw = author_info.get("orcid")
            orcid = orcid_raw.replace("https://orcid.org/", "") if orcid_raw else None
            institutions = authorship.get("institutions") or []
            institution = institutions[0] if institutions else {}
            country = _institution_country(institution)
            affiliation = institution.get("display_name")
            if affiliation and country:
                affiliation = f"{affiliation}, {country}"
            authors.append(RawAuthor(name=name, orcid=orcid, affiliation=affiliation, country=country))

        abstract = self._reconstruct_abstract(work.get("abstract_inverted_index"))
        keywords = [kw["display_name"] for kw in work.get("keywords", [])]
        references = [self._extract_id(ref) for ref in work.get("referenced_works", [])]

        return RawRecord(
            source_id=self._extract_id(work.get("id", "")),
            source_database="openalex",
            title=work.get("title", ""),
            abstract=abstract,
            doi=external_ids.get("doi"),
            year=work.get("publication_year"),
            journal_name=source.get("display_name"),
            journal_issn=source.get("issn_l"),
            publication_type=work.get("type"),
            authors=authors,
            mesh_terms=[],
            keywords=keywords,
            references=references,
            external_ids=external_ids,
        )

    @staticmethod
    def _extract_id(url: str) -> str:
        return url.split("/")[-1] if "/" in url else url

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
        if not inverted_index:
            return None
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join(word for _, word in word_positions)

    async def close(self) -> None:
        await self._client.aclose()
