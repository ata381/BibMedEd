"""Offline Europe PMC test double shared by the Europe PMC adapter tests.

Requests are intercepted at ``httpx.AsyncHTTPTransport`` so the tests stay agnostic
to how the adapter builds its client and whether it uses ``GET /search`` or
``POST /searchPOST``. Anything that is not a Europe PMC search call fails loudly,
and no request can reach the network.
"""

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
MAX_REQUESTS = 50
# The docs publish www.ebi.ac.uk; the generated OpenAPI spec lists the second host.
EUROPEPMC_HOSTS = {"www.ebi.ac.uk", "rest-api-live.europepmc.org"}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def search_pages() -> dict[str, dict]:
    return copy.deepcopy(load_fixture("europepmc_search_idlist.json")["pages"])


def core_records() -> list[dict]:
    return copy.deepcopy(load_fixture("europepmc_core_records.json")["resultList"]["result"])


def core_record(source: str, record_id: str) -> dict:
    return next(r for r in core_records() if r["source"] == source and r["id"] == record_id)


@dataclass
class SeenRequest:
    method: str
    path: str
    params: dict[str, str]

    @property
    def query(self) -> str:
        return self.params.get("query", "")

    @property
    def result_type(self) -> str:
        return self.params.get("resultType", "lite")


def _request_params(request: httpx.Request) -> dict[str, str]:
    params = dict(request.url.params.multi_items())
    if request.method == "POST":
        content_type = request.headers.get("content-type", "")
        body = request.content.decode()
        if "application/x-www-form-urlencoded" in content_type:
            params.update(parse_qsl(body, keep_blank_values=True))
        elif body:
            raise AssertionError(
                f"searchPOST is documented as form-encoded; got content-type {content_type!r}"
            )
    return params


def _mentions_id(query: str, record_id: str) -> bool:
    return re.search(rf"(?<![\w.]){re.escape(record_id)}(?![\w.])", query, re.IGNORECASE) is not None


class FakeEuropePMC:
    """Serves idlist pages keyed by ``cursorMark`` and core records selected by the
    identifiers that appear in the query text, paged by ``pageSize``."""

    def __init__(
        self,
        *,
        pages: dict[str, dict] | None = None,
        records: list[dict] | None = None,
        unrequested_extras: list[dict] | None = None,
        core_payload: object | None = None,
        raw_body: str | None = None,
        status_code: int = 200,
    ):
        self.pages = pages if pages is not None else search_pages()
        self.records = records if records is not None else core_records()
        self.unrequested_extras = unrequested_extras or []
        self.core_payload = core_payload
        self.raw_body = raw_body
        self.status_code = status_code
        self.requests: list[SeenRequest] = []

    @property
    def search_requests(self) -> list[SeenRequest]:
        return [r for r in self.requests if r.result_type != "core"]

    @property
    def core_requests(self) -> list[SeenRequest]:
        return [r for r in self.requests if r.result_type == "core"]

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host not in EUROPEPMC_HOSTS or not re.search(
            r"/europepmc/webservices/rest/(search|searchPOST)$", request.url.path
        ):
            raise AssertionError(f"Unexpected request outside the Europe PMC search API: {request.url}")
        seen = SeenRequest(request.method, request.url.path, _request_params(request))
        self.requests.append(seen)
        if len(self.requests) > MAX_REQUESTS:
            raise AssertionError("Adapter issued too many requests; pagination is not terminating")
        if self.status_code != 200:
            return httpx.Response(self.status_code, json={"errMsg": "synthetic failure"}, request=request)
        if self.raw_body is not None:
            return httpx.Response(200, text=self.raw_body, headers={"content-type": "application/json"},
                                  request=request)
        if seen.result_type == "core":
            return httpx.Response(200, json=self._core(seen), request=request)
        return httpx.Response(200, json=self._page(seen), request=request)

    def _page(self, seen: SeenRequest) -> object:
        cursor = seen.params.get("cursorMark") or "*"
        if cursor not in self.pages:
            raise AssertionError(f"Adapter sent unknown cursorMark {cursor!r}")
        return self.pages[cursor]

    def _core(self, seen: SeenRequest) -> object:
        if self.core_payload is not None:
            return self.core_payload
        matches = [r for r in self.records if _mentions_id(seen.query, r["id"])]
        matches += self.unrequested_extras
        page_size = int(seen.params.get("pageSize", "25"))
        cursor = seen.params.get("cursorMark") or "*"
        offset = 0 if cursor == "*" else int(cursor.removeprefix("FAKECORE"))
        chunk = matches[offset:offset + page_size]
        next_offset = offset + len(chunk)
        return {
            "version": "6.9",
            "hitCount": len(matches),
            "nextCursorMark": f"FAKECORE{next_offset}" if next_offset < len(matches) else cursor,
            "request": {"queryString": seen.query, "resultType": "core", "cursorMark": cursor},
            "resultList": {"result": chunk},
        }


@pytest.fixture
def fake_epmc(monkeypatch) -> FakeEuropePMC:
    fake = FakeEuropePMC()

    async def handle_async_request(transport, request):
        return fake.handle(request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle_async_request)
    return fake


@pytest.fixture
def tracked_clients(monkeypatch) -> list[httpx.AsyncClient]:
    created: list[httpx.AsyncClient] = []
    original_init = httpx.AsyncClient.__init__

    def tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", tracking_init)
    return created
