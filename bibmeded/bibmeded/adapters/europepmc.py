"""Europe PMC REST adapter.

No API key is required. Searches use ``resultType=idlist`` with ``cursorMark``
pagination; records are fetched in batches with ``resultType=core`` through the
form-encoded ``POST /searchPOST`` endpoint, which accepts the same parameters as
``GET /search`` without URL-length limits on long queries.

Europe PMC identifiers are only unique within a source collection (MED, PMC, PPR,
...), so the adapter's ``source_id`` is the composite ``"<SRC>:<id>"``.

Docs: https://europepmc.org/RestfulWebService
API schema: https://www.ebi.ac.uk/europepmc/webservices/rest/v3/api-docs
"""

import html
import re
from collections.abc import AsyncGenerator, Callable, Iterable
from html.parser import HTMLParser

import httpx

from bibmeded.adapters.base import BaseSourceAdapter, RawAuthor, RawRecord, SearchResponse

EUROPEPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_SEARCH_PAGE_SIZE = 1000
_FETCH_BATCH_SIZE = 100
_MAX_REPORTED_MISSING = 10
# Collections documented by Europe PMC. Each was checked to round-trip through
# `EXT_ID:<id> AND SRC:<SRC>` (tests/fixtures/europepmc_real_PROVENANCE.md).
_SOURCES = frozenset({"MED", "PMC", "PAT", "AGR", "CBA", "HIR", "CTX", "ETH", "CIT", "PPR", "NBK"})
# IDs are interpolated into a Lucene query, so only plain identifier characters pass.
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._]*")
_YEAR = re.compile(r"\d{4}")
_PMCID = re.compile(r"PMC\d+")
_ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
_BLOCK_TAGS = frozenset({
    "address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "figure",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "li", "ol", "p", "pre", "section", "table",
    "td", "th", "tr", "ul",
})
_INLINE_TAGS = frozenset({
    "a", "abbr", "b", "cite", "code", "em", "font", "i", "q", "s", "small", "span", "strong",
    "sub", "sup", "u", "var",
})
_DISCARDED_CONTENT_TAGS = frozenset({"script", "style"})


class EuropePMCResponseError(RuntimeError):
    """Europe PMC answered, but not with a usable result envelope."""


class EuropePMCPaginationError(EuropePMCResponseError):
    """Pagination ended, repeated, or overran before matching the reported hitCount."""


class EuropePMCIncompleteFetchError(EuropePMCResponseError):
    """A record batch came back without some of the requested records."""


def _text(value: object) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


class _AbstractTextParser(HTMLParser):
    """Europe PMC serves structured abstracts as HTML (``<h4>`` section headings,
    ``<p>``, ``<br>``, inline ``<i>``/``<sub>``). Each heading or paragraph becomes
    one line so sections stay apart once exporters flatten line breaks. Every tag
    ``HTMLParser`` recognises is dropped: known inline tags join their text, other
    unknown tags act as a word boundary, and ``script``/``style`` contents are
    discarded. ``<`` that does not open a tag (``p<0.05``, ``n < 3``) stays text, but
    a literal word in angle brackets (``<placebo>`` unescaped) is a tag to the parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.saw_markup = False
        self._lines: list[str] = []
        self._current: list[str] = []
        self._skipping: str | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._tag(tag)
        if tag in _DISCARDED_CONTENT_TAGS:
            self._skipping = tag

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        self._tag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._skipping:
            self._skipping = None
        self._tag(tag)

    def handle_data(self, data: str) -> None:
        if self._skipping is None:
            self._current.append(data)

    def handle_comment(self, data: str) -> None:
        self.saw_markup = True

    def handle_decl(self, decl: str) -> None:
        self.saw_markup = True

    def handle_pi(self, data: str) -> None:
        self.saw_markup = True

    def text(self) -> str | None:
        # CPython drops a tag left unterminated at end of input (HTML5 EOF rule);
        # in an abstract that is literal text such as a trailing "n<b".
        if "<" in self.rawdata and ">" not in self.rawdata:
            self.handle_data(html.unescape(self.rawdata))
            self.rawdata = ""
        self.close()
        self._end_line()
        return "\n".join(self._lines) or None

    def _tag(self, tag: str) -> None:
        self.saw_markup = True
        if tag in _BLOCK_TAGS:
            self._end_line()
        elif tag not in _INLINE_TAGS and self._skipping is None:
            self._current.append(" ")

    def _end_line(self) -> None:
        line = " ".join("".join(self._current).split())
        if line:
            self._lines.append(line)
        self._current = []


def _abstract(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    parser = _AbstractTextParser()
    parser.feed(text)
    if not parser.saw_markup:
        return _text(html.unescape(text))
    return parser.text()


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _normalize_doi(value: object) -> str | None:
    doi = _text(value)
    if not doi:
        return None
    doi = doi.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi.removeprefix(prefix).strip()
            break
    return doi or None


def _normalize_pmid(value: object) -> str | None:
    pmid = _text(str(value)) if isinstance(value, int) and not isinstance(value, bool) else _text(value)
    return pmid if pmid and pmid.isascii() and pmid.isdecimal() else None


def _normalize_pmcid(value: object) -> str | None:
    pmcid = _text(value)
    if not pmcid:
        return None
    pmcid = pmcid.upper()
    return pmcid if _PMCID.fullmatch(pmcid) else None


def _normalize_orcid(value: object) -> str | None:
    orcid = _text(value)
    if not orcid:
        return None
    orcid = orcid.rstrip("/").rsplit("/", 1)[-1].upper()
    return orcid if _ORCID.fullmatch(orcid) else None


def _year(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 1000 <= value <= 9999 else None
    text = _text(value)
    return int(text) if text and _YEAR.fullmatch(text) else None


def _year_bound(value: object, label: str) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    text = str(value).strip()
    if not _YEAR.fullmatch(text):
        raise ValueError(f"Europe PMC {label} must be a four-digit year, got {value!r}")
    return text


def _is_fetchable(source: str, record_id: str) -> bool:
    return source in _SOURCES and _SAFE_ID.fullmatch(record_id) is not None


def _split_composite_id(composite: object) -> tuple[str, str]:
    source, sep, record_id = composite.partition(":") if isinstance(composite, str) else ("", "", "")
    if not sep or not _is_fetchable(source, record_id):
        raise ValueError(f"Europe PMC cannot fetch malformed id {composite!r}")
    return source, record_id


def _result_key(item: object) -> tuple[str, str] | None:
    if not isinstance(item, dict):
        return None
    source, record_id = _text(item.get("source")), _text(item.get("id"))
    if not source or not record_id:
        return None
    return source, record_id


class EuropePMCAdapter(BaseSourceAdapter):
    name = "europepmc"
    display_name = "Europe PMC"
    requires_api_key = False

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def search(self, query: str, **kwargs) -> SearchResponse:
        query = self._filtered_query(query, kwargs)
        total, results, _ = await self._search_page(query, "idlist", "*", _SEARCH_PAGE_SIZE)
        self._check_page_counts(total, 0, results)
        return SearchResponse(total_count=total, ids=self._composite_ids(results, set()))

    async def search_paginated(self, query: str, **kwargs) -> AsyncGenerator[list[str], None]:
        """Every yielded ID is unique and fetchable, and yielded IDs add up to the
        first page's hitCount; anything else raises rather than looking complete."""
        self.upstream_total = None
        query = self._filtered_query(query, kwargs)
        delivered: set[str] = set()
        async for results in self._paged(query, "idlist", _SEARCH_PAGE_SIZE, on_total=self._set_upstream_total):
            yield self._composite_ids(results, delivered)

    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        """Return one record per requested ID or raise ``EuropePMCIncompleteFetchError``."""
        keys = list(dict.fromkeys(_split_composite_id(composite) for composite in ids))
        records: list[RawRecord] = []
        for start in range(0, len(keys), _FETCH_BATCH_SIZE):
            batch = keys[start:start + _FETCH_BATCH_SIZE]
            missing = set(batch)
            query = " OR ".join(f"(EXT_ID:{record_id} AND SRC:{source})" for source, record_id in batch)
            async for results in self._paged(query, "core", _FETCH_BATCH_SIZE):
                for item in results:
                    key = _result_key(item)
                    if key in missing:
                        missing.discard(key)
                        records.append(self._to_raw(item, key))
            if missing:
                raise self._incomplete_fetch_error(len(batch), missing)
        return records

    async def close(self) -> None:
        await self._client.aclose()

    def _set_upstream_total(self, total: int) -> None:
        self.upstream_total = total

    @staticmethod
    def _filtered_query(query: str, kwargs: dict) -> str:
        start = _year_bound(kwargs.get("year_start"), "year_start")
        end = _year_bound(kwargs.get("year_end"), "year_end")
        if not start and not end:
            return query
        return f"({query}) AND PUB_YEAR:[{start or '*'} TO {end or '*'}]"

    @staticmethod
    def _composite_ids(results: Iterable[object], delivered: set[str]) -> list[str]:
        ids = []
        for position, item in enumerate(results):
            key = _result_key(item)
            if key is None or not _is_fetchable(*key):
                raise EuropePMCResponseError(
                    f"Europe PMC search result {position} has no fetchable source/id: {str(item)[:120]}"
                )
            composite = f"{key[0]}:{key[1]}"
            if composite in delivered:
                raise EuropePMCPaginationError(f"Europe PMC search returned duplicate id {composite}")
            delivered.add(composite)
            ids.append(composite)
        return ids

    @staticmethod
    def _check_page_counts(total: int, seen_before: int, results: list) -> None:
        if not results and seen_before < total:
            raise EuropePMCPaginationError(
                f"Europe PMC returned an empty page after {seen_before} of {total} results"
            )
        if seen_before + len(results) > total:
            raise EuropePMCPaginationError(
                f"Europe PMC returned {seen_before + len(results)} results but reported hitCount {total}"
            )

    @staticmethod
    def _incomplete_fetch_error(requested: int, missing: set[tuple[str, str]]) -> EuropePMCIncompleteFetchError:
        names = sorted(f"{source}:{record_id}" for source, record_id in missing)
        shown = ", ".join(names[:_MAX_REPORTED_MISSING])
        more = f" and {len(names) - _MAX_REPORTED_MISSING} more" if len(names) > _MAX_REPORTED_MISSING else ""
        return EuropePMCIncompleteFetchError(
            f"Europe PMC returned {requested - len(missing)} of {requested} requested records; "
            f"missing {shown}{more}"
        )

    async def _paged(
        self, query: str, result_type: str, page_size: int,
        on_total: Callable[[int], None] | None = None,
    ) -> AsyncGenerator[list, None]:
        """Yield each page's results until the first page's hitCount is reached. An
        empty page, an overrun, or a cursor that stops advancing before then raises:
        it is an interrupted pagination, not a finished one."""
        cursor = "*"
        seen_cursors = {cursor}
        seen_results = 0
        total: int | None = None
        while True:
            page_total, results, next_cursor = await self._search_page(query, result_type, cursor, page_size)
            if total is None:
                total = page_total
                if on_total is not None:
                    on_total(total)
            self._check_page_counts(total, seen_results, results)
            if not results:
                return
            seen_results += len(results)
            yield results
            if seen_results >= total:
                return
            if not next_cursor or next_cursor in seen_cursors:
                raise EuropePMCPaginationError(
                    f"Europe PMC pagination stopped after {seen_results} of {total} results: "
                    f"cursorMark {next_cursor!r} did not advance from {cursor!r}"
                )
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    async def _search_page(
        self, query: str, result_type: str, cursor: str, page_size: int,
    ) -> tuple[int, list, str | None]:
        resp = await self._client.post(
            f"{EUROPEPMC_API}/searchPOST",
            data={
                "query": query,
                "resultType": result_type,
                "format": "json",
                "pageSize": str(page_size),
                "cursorMark": cursor,
            },
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            raise EuropePMCResponseError("Europe PMC returned a non-JSON response") from exc
        return self._parse_envelope(data)

    @staticmethod
    def _parse_envelope(data: object) -> tuple[int, list, str | None]:
        if not isinstance(data, dict):
            raise EuropePMCResponseError("Europe PMC response is not a JSON object")
        if "errCode" in data or "errMsg" in data:
            message = str(data.get("errMsg") or data.get("errCode"))[:200]
            raise EuropePMCResponseError(f"Europe PMC reported an error: {message}")
        total = data.get("hitCount")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise EuropePMCResponseError("Europe PMC response has no valid hitCount")
        result_list = data.get("resultList")
        if result_list is None and total == 0:
            return 0, [], None
        results = result_list.get("result") if isinstance(result_list, dict) else None
        if not isinstance(results, list):
            raise EuropePMCResponseError("Europe PMC response has no resultList.result array")
        return total, results, _text(data.get("nextCursorMark"))

    @staticmethod
    def _to_raw(item: dict, key: tuple[str, str]) -> RawRecord:
        source, record_id = key
        composite = f"{source}:{record_id}"

        doi = _normalize_doi(item.get("doi"))
        pmid = _normalize_pmid(item.get("pmid")) or (_normalize_pmid(record_id) if source == "MED" else None)
        pmcid = _normalize_pmcid(item.get("pmcid")) or (_normalize_pmcid(record_id) if source == "PMC" else None)
        external_ids = {"europepmc": composite}
        if doi:
            external_ids["doi"] = doi
        if pmid:
            external_ids["pmid"] = pmid
        if pmcid:
            external_ids["pmcid"] = pmcid

        journal_info = _dict(item.get("journalInfo"))
        journal = _dict(journal_info.get("journal"))
        book = _dict(item.get("bookOrReportDetails"))
        pub_types = [t for t in (_text(v) for v in _list(_dict(item.get("pubTypeList")).get("pubType"))) if t]

        return RawRecord(
            source_id=composite,
            source_database="europepmc",
            title=_text(item.get("title")) or "",
            abstract=_abstract(item.get("abstractText")),
            doi=doi,
            year=(_year(item.get("pubYear")) or _year(journal_info.get("yearOfPublication"))
                  or _year(book.get("yearOfPublication"))),
            journal_name=_text(journal.get("title")),
            journal_issn=_text(journal.get("issn")) or _text(journal.get("essn")),
            publication_type=pub_types[0] if pub_types else _text(item.get("pubType")),
            authors=EuropePMCAdapter._authors(item),
            mesh_terms=[
                term for term in (
                    _text(_dict(h).get("descriptorName"))
                    for h in _list(_dict(item.get("meshHeadingList")).get("meshHeading"))
                ) if term
            ],
            keywords=[kw for kw in (_text(k) for k in _list(_dict(item.get("keywordList")).get("keyword"))) if kw],
            references=[],
            external_ids=external_ids,
        )

    @staticmethod
    def _authors(item: dict) -> list[RawAuthor]:
        authors = []
        for raw in _list(_dict(item.get("authorList")).get("author")):
            author = _dict(raw)
            name = _text(author.get("fullName")) or _text(author.get("collectiveName"))
            if not name:
                continue
            author_id = _dict(author.get("authorId"))
            orcid = None
            if (_text(author_id.get("type")) or "").upper() == "ORCID":
                orcid = _normalize_orcid(author_id.get("value"))
            affiliations = _list(_dict(author.get("authorAffiliationDetailsList")).get("authorAffiliation"))
            affiliation = next(
                (a for a in (_text(_dict(entry).get("affiliation")) for entry in affiliations) if a), None,
            )
            authors.append(RawAuthor(name=name, orcid=orcid, affiliation=affiliation))
        return authors
