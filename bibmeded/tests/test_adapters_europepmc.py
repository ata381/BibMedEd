"""Contract tests for the Europe PMC adapter (issue #7).

All HTTP traffic is served by ``tests/europepmc_fake.py`` from synthetic fixtures and
minimised captured payloads (``fixtures/europepmc_real_PROVENANCE.md``).

Error contract: an empty but well-formed response is an empty result; an HTTP error,
malformed body, ``errCode``/``errMsg`` payload, or inconsistent pagination raises, so
an API failure can never be recorded as a legitimately empty or completed search.
Failures raised by the adapter itself are ``RuntimeError`` subclasses naming Europe PMC.
"""

import asyncio
import copy
import re
from pathlib import Path

import httpx
import pytest

from bibmeded.adapters.base import BaseSourceAdapter, RawRecord, SearchResponse
from bibmeded.adapters.europepmc import EuropePMCAdapter
from tests.europepmc_fake import (  # noqa: F401 — pytest fixtures
    FakeEuropePMC,
    core_record,
    fake_epmc,
    load_fixture,
    tracked_clients,
)

MED_FULL = "MED:99000001"
PPR = "PPR:PPR990001"
MED_MINIMAL = "MED:99000002"
PMC_ONLY = "PMC:PMC99000009"
ALL_FIXTURE_IDS = [MED_FULL, PPR, MED_MINIMAL, PMC_ONLY]
ADAPTER_ERROR = (RuntimeError, "Europe PMC")


@pytest.fixture
def adapter_cls():
    return EuropePMCAdapter


@pytest.fixture
def adapter(adapter_cls, fake_epmc):
    instance = adapter_cls()
    yield instance
    asyncio.run(instance.close())


def _collect(adapter, query: str, **kwargs) -> list[list[str]]:
    async def run():
        return [batch async for batch in adapter.search_paginated(query, **kwargs)]
    return asyncio.run(run())


def _collect_until_error(adapter, query: str) -> tuple[list[list[str]], BaseException]:
    batches: list[list[str]] = []

    async def run():
        async for batch in adapter.search_paginated(query):
            batches.append(batch)

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]) as excinfo:
        asyncio.run(run())
    return batches, excinfo.value


def _fetch(adapter, ids: list[str]) -> list[RawRecord]:
    return asyncio.run(adapter.fetch(ids))


def _fetch_one(adapter, fake: FakeEuropePMC, record: dict) -> RawRecord:
    fake.records = [record]
    records = _fetch(adapter, [f"{record['source']}:{record['id']}"])
    assert len(records) == 1
    return records[0]


def _by_source_id(records: list[RawRecord]) -> dict[str, RawRecord]:
    return {r.source_id: r for r in records}


def _page(ids: list[tuple[str, str]], *, hit_count: int, next_cursor: object = "absent") -> dict:
    page: dict = {"hitCount": hit_count, "resultList": {"result": [{"id": i, "source": s} for s, i in ids]}}
    if next_cursor != "absent":
        page["nextCursorMark"] = next_cursor
    return page


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------

def test_adapter_metadata(adapter_cls):
    assert issubclass(adapter_cls, BaseSourceAdapter)
    assert adapter_cls.name == "europepmc"
    assert adapter_cls.display_name == "Europe PMC"
    assert adapter_cls.requires_api_key is False


def test_adapter_constructs_without_credentials(adapter):
    assert adapter.methodology_label() == "Europe PMC API"


# ---------------------------------------------------------------------------
# A. Search and pagination
# ---------------------------------------------------------------------------

def test_search_returns_first_page_composite_ids_and_hit_count(adapter, fake_epmc):
    result = asyncio.run(adapter.search("medical education"))

    assert isinstance(result, SearchResponse)
    assert result.total_count == 5000
    assert result.ids == [MED_FULL, PPR, MED_MINIMAL]
    assert len(fake_epmc.requests) == 1


def test_search_requests_json_idlist_within_page_limit(adapter, fake_epmc):
    asyncio.run(adapter.search("medical education"))

    params = fake_epmc.requests[0].params
    assert params.get("format") == "json"
    assert params.get("resultType") == "idlist"
    assert params.get("cursorMark", "*") == "*"
    assert 1 <= int(params["pageSize"]) <= 1000


def test_search_paginated_follows_next_cursor_mark_until_hit_count(adapter, fake_epmc):
    for page in fake_epmc.pages.values():
        page["hitCount"] = 6

    batches = _collect(adapter, "medical education")

    assert batches == [
        [MED_FULL, PPR, MED_MINIMAL],
        [PMC_ONLY, "MED:99000003", "MED:99000004"],
    ]
    assert [r.params.get("cursorMark", "*") for r in fake_epmc.requests] == ["*", "AoIIP0SYNTH01"]


def test_search_paginated_raises_on_empty_page_before_hit_count(adapter, fake_epmc):
    batches, error = _collect_until_error(adapter, "medical education")

    assert batches == [
        [MED_FULL, PPR, MED_MINIMAL],
        [PMC_ONLY, "MED:99000003", "MED:99000004"],
    ]
    assert "6" in str(error) and "5000" in str(error)
    assert len(fake_epmc.requests) == 3


def test_search_paginated_keeps_first_page_hit_count_as_upstream_total(adapter, fake_epmc):
    _collect_until_error(adapter, "medical education")

    assert adapter.upstream_total == 5000


def test_search_paginated_resets_upstream_total_and_propagates_http_errors(adapter, fake_epmc):
    adapter.upstream_total = 123
    fake_epmc.status_code = 503

    with pytest.raises(httpx.HTTPStatusError):
        _collect(adapter, "medical education")
    assert adapter.upstream_total is None


def test_search_paginated_empty_first_page_yields_nothing(adapter, fake_epmc):
    fake_epmc.pages = {"*": _page([], hit_count=0, next_cursor="*")}

    assert _collect(adapter, "no such topic") == []
    assert adapter.upstream_total == 0
    assert len(fake_epmc.requests) == 1


@pytest.mark.parametrize("next_cursor", ["absent", "", "*"])
def test_search_paginated_completes_without_cursor_once_hit_count_is_reached(
    adapter, fake_epmc, next_cursor
):
    fake_epmc.pages = {"*": _page([("MED", "1"), ("MED", "2")], hit_count=2, next_cursor=next_cursor)}

    assert _collect(adapter, "q") == [["MED:1", "MED:2"]]
    assert len(fake_epmc.requests) == 1


@pytest.mark.parametrize("next_cursor", ["absent", "", "*"])
def test_search_paginated_raises_when_cursor_ends_before_hit_count(adapter, fake_epmc, next_cursor):
    fake_epmc.pages = {"*": _page([("MED", "1"), ("MED", "2")], hit_count=5, next_cursor=next_cursor)}

    batches, error = _collect_until_error(adapter, "q")

    assert batches == [["MED:1", "MED:2"]]
    assert "2" in str(error) and "5" in str(error)
    assert len(fake_epmc.requests) == 1


def test_search_paginated_raises_when_cursor_cycles(adapter, fake_epmc):
    fake_epmc.pages = {
        "*": _page([("MED", "1")], hit_count=10, next_cursor="A"),
        "A": _page([("MED", "2")], hit_count=10, next_cursor="B"),
        "B": _page([("MED", "3")], hit_count=10, next_cursor="A"),
    }

    batches, _ = _collect_until_error(adapter, "q")

    assert batches == [["MED:1"], ["MED:2"], ["MED:3"]]
    assert len(fake_epmc.requests) == 3


@pytest.mark.parametrize(
    "bad_item",
    [{"id": "99000077"}, {"source": "MED"}, {"id": "", "source": "MED"}, "x",
     {"id": "1 OR SRC:PPR", "source": "MED"}, {"id": "1", "source": "XYZ"}, {"id": "1", "source": "med"}],
    ids=["no-source", "no-id", "blank-id", "not-a-dict", "lucene-in-id", "unknown-collection", "lowercase-src"],
)
def test_search_rejects_results_without_a_fetchable_identity(adapter, fake_epmc, bad_item):
    page = _page([("MED", "1")], hit_count=2, next_cursor="*")
    page["resultList"]["result"].append(bad_item)
    fake_epmc.pages = {"*": page}

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _collect(adapter, "q")
    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        asyncio.run(adapter.search("q"))


def test_search_rejects_duplicate_ids_within_a_page(adapter, fake_epmc):
    fake_epmc.pages = {"*": _page([("MED", "1"), ("MED", "1")], hit_count=2, next_cursor="*")}

    with pytest.raises(ADAPTER_ERROR[0], match="duplicate"):
        _collect(adapter, "q")


def test_search_rejects_duplicate_ids_across_pages(adapter, fake_epmc):
    fake_epmc.pages = {
        "*": _page([("MED", "1"), ("MED", "2")], hit_count=4, next_cursor="A"),
        "A": _page([("MED", "2"), ("MED", "3")], hit_count=4, next_cursor="B"),
    }

    batches, error = _collect_until_error(adapter, "q")

    assert batches == [["MED:1", "MED:2"]]
    assert "duplicate" in str(error) and "MED:2" in str(error)


def test_same_number_in_different_collections_is_not_a_duplicate(adapter, fake_epmc):
    fake_epmc.pages = {"*": _page([("MED", "1"), ("CBA", "1")], hit_count=2, next_cursor="*")}

    assert _collect(adapter, "q") == [["MED:1", "CBA:1"]]


def test_search_rejects_results_when_hit_count_is_zero(adapter, fake_epmc):
    fake_epmc.pages = {"*": _page([("MED", "1")], hit_count=0, next_cursor="*")}

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _collect(adapter, "q")
    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        asyncio.run(adapter.search("q"))


def test_search_rejects_more_results_than_hit_count_across_pages(adapter, fake_epmc):
    fake_epmc.pages = {
        "*": _page([("MED", "1"), ("MED", "2")], hit_count=3, next_cursor="A"),
        "A": _page([("MED", "3"), ("MED", "4")], hit_count=3, next_cursor="B"),
    }

    batches, error = _collect_until_error(adapter, "q")

    assert batches == [["MED:1", "MED:2"]]
    assert "4" in str(error) and "3" in str(error)


def test_search_rejects_empty_first_page_with_positive_hit_count(adapter, fake_epmc):
    fake_epmc.pages = {"*": _page([], hit_count=3)}

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _collect(adapter, "q")


DOCUMENTED_COLLECTIONS = [
    ("MED", "42954961"), ("PMC", "PMC13787573"), ("PAT", "CN101548780"), ("AGR", "IND44331483"),
    ("CBA", "367763"), ("HIR", "410369"), ("CTX", "C8501"), ("ETH", "889149"), ("CIT", "711268"),
    ("PPR", "PPR1373820"), ("NBK", "NBK623779"),
]


def test_search_keeps_every_documented_collection(adapter, fake_epmc):
    fake_epmc.pages = {"*": _page(DOCUMENTED_COLLECTIONS, hit_count=11)}

    assert _collect(adapter, "q") == [[f"{s}:{i}" for s, i in DOCUMENTED_COLLECTIONS]]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"hitCount": 3},
        {"hitCount": 3, "resultList": None},
        {"hitCount": 3, "resultList": {"result": "unexpected"}},
        {"hitCount": "many", "resultList": {"result": []}},
        {"resultList": {"result": [{"id": "1", "source": "MED"}]}},
        [],
    ],
    ids=["empty", "no-result-list", "null-result-list", "string-result", "bad-hit-count",
         "no-hit-count", "top-level-array"],
)
def test_search_rejects_structurally_invalid_envelopes(adapter, fake_epmc, payload):
    fake_epmc.pages = {"*": copy.deepcopy(payload)}

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _collect(adapter, "q")
    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        asyncio.run(adapter.search("q"))


@pytest.mark.parametrize("payload", [
    {"errCode": 400, "errMsg": "Invalid query syntax"},
    {"hitCount": 0, "errMsg": "Search service unavailable", "resultList": {"result": []}},
])
def test_search_raises_on_api_error_payload(adapter, fake_epmc, payload):
    fake_epmc.pages = {"*": payload}

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _collect(adapter, "q")


def test_search_raises_on_invalid_json(adapter, fake_epmc):
    fake_epmc.raw_body = "<html>upstream proxy error</html>"

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _collect(adapter, "q")


def _year_bounds(query: str) -> tuple[str, str] | None:
    match = re.search(r"PUB_YEAR:\[\s*(\S+)\s+TO\s+(\S+?)\s*\]", query, re.IGNORECASE)
    return (match.group(1), match.group(2)) if match else None


def _is_open_upper(bound: str) -> bool:
    return bound == "*" or (bound.isdigit() and int(bound) >= 3000)


def _is_open_lower(bound: str) -> bool:
    return bound == "*" or (bound.isdigit() and int(bound) <= 1000)


@pytest.mark.parametrize(
    "year_start,year_end",
    [("2020", "2024"), ("2020", None), (None, "2024"), ("2021", "2021")],
)
def test_year_filters_add_pub_year_range_around_grouped_user_query(adapter, fake_epmc, year_start, year_end):
    user_query = "simulation OR curriculum"
    fake_epmc.pages = {"*": _page([("MED", "1")], hit_count=1)}
    _collect(adapter, user_query, year_start=year_start, year_end=year_end)

    sent = fake_epmc.requests[0].query
    bounds = _year_bounds(sent)
    assert bounds is not None, sent
    lower, upper = bounds
    assert lower == year_start if year_start else _is_open_lower(lower), sent
    assert upper == year_end if year_end else _is_open_upper(upper), sent
    assert f"({user_query})" in sent, "user query must be parenthesised before AND-ing the year range"


@pytest.mark.parametrize("year_start,year_end", [(None, None), ("", "")])
def test_no_year_filter_sends_user_query_unchanged(adapter, fake_epmc, year_start, year_end):
    fake_epmc.pages = {"*": _page([("MED", "1")], hit_count=1)}
    _collect(adapter, "simulation OR curriculum", year_start=year_start, year_end=year_end)

    assert fake_epmc.requests[0].query == "simulation OR curriculum"


@pytest.mark.parametrize("bad_year", ["20x0", "2020] OR (*", "99", "2020-01-01"])
def test_non_year_filter_values_are_rejected_before_any_request(adapter, fake_epmc, bad_year):
    with pytest.raises(ValueError):
        _collect(adapter, "q", year_start=bad_year)
    assert fake_epmc.requests == []


# ---------------------------------------------------------------------------
# B. Record retrieval
# ---------------------------------------------------------------------------

def test_fetch_retrieves_multiple_records_in_one_core_request(adapter, fake_epmc):
    records = _fetch(adapter, ALL_FIXTURE_IDS)

    assert sorted(r.source_id for r in records) == sorted(ALL_FIXTURE_IDS)
    assert all(isinstance(r, RawRecord) and r.source_database == "europepmc" for r in records)
    assert len(fake_epmc.core_requests) == 1
    assert fake_epmc.requests == fake_epmc.core_requests
    assert fake_epmc.core_requests[0].params.get("format") == "json"


def test_fetch_uses_form_encoded_search_post(adapter, fake_epmc):
    _fetch(adapter, [MED_FULL])

    request = fake_epmc.core_requests[0]
    assert request.method == "POST"
    assert request.path.endswith("/searchPOST")


def test_fetch_query_pins_each_id_to_its_source(adapter, fake_epmc):
    _fetch(adapter, [MED_FULL, PPR, PMC_ONLY])

    sent = fake_epmc.core_requests[0].query
    for source, record_id in (("MED", "99000001"), ("PPR", "PPR990001"), ("PMC", "PMC99000009")):
        clause = rf'\(\s*EXT_ID:"?{record_id}"?\s+AND\s+SRC:"?{source}"?\s*\)'
        assert re.search(clause, sent, re.IGNORECASE), sent


def test_fetch_worker_sized_batch_does_not_issue_one_request_per_record(adapter, fake_epmc):
    template = core_record("MED", "99000002")
    fake_epmc.records = [
        {**template, "id": str(98000000 + i), "pmid": str(98000000 + i)} for i in range(200)
    ]
    ids = [f"MED:{98000000 + i}" for i in range(200)]

    records = _fetch(adapter, ids)

    assert sorted(r.source_id for r in records) == sorted(ids)
    assert 1 <= len(fake_epmc.core_requests) <= 4
    assert fake_epmc.requests == fake_epmc.core_requests


def test_fetch_stream_covers_every_id(adapter, fake_epmc):
    async def run():
        return [chunk async for chunk in adapter.fetch_stream(ALL_FIXTURE_IDS, batch_size=2)]

    chunks = asyncio.run(run())

    assert sorted(r.source_id for chunk in chunks for r in chunk) == sorted(ALL_FIXTURE_IDS)


def test_fetch_empty_id_list_makes_no_request(adapter, fake_epmc):
    assert _fetch(adapter, []) == []
    assert fake_epmc.requests == []


@pytest.mark.parametrize("bad_id", ["99000001", "MED:", ":99000001", "XYZ:1", "MED:1 OR SRC:PPR", 'MED:1")'])
def test_fetch_rejects_malformed_or_unsafe_ids_before_any_request(adapter, fake_epmc, bad_id):
    with pytest.raises(ValueError):
        _fetch(adapter, [MED_FULL, bad_id])
    assert fake_epmc.requests == []


def test_fetch_keeps_composite_identity_and_drops_unrequested_hits(adapter, fake_epmc):
    same_number_other_source = {**core_record("MED", "99000001"), "source": "CTX", "pmid": None}
    unrelated = {"id": "99000500", "source": "MED", "pmid": "99000500", "title": "Not requested"}
    fake_epmc.unrequested_extras = [same_number_other_source, unrelated]

    records = _fetch(adapter, [MED_FULL])

    assert [r.source_id for r in records] == [MED_FULL]


def test_fetch_raises_when_a_requested_record_is_missing(adapter, fake_epmc):
    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]) as excinfo:
        _fetch(adapter, [MED_FULL, "MED:99000999"])

    assert "MED:99000999" in str(excinfo.value)
    assert "1 of 2" in str(excinfo.value)


def test_fetch_raises_on_valid_but_empty_response(adapter, fake_epmc):
    fake_epmc.core_payload = {"hitCount": 0, "resultList": {"result": []}}

    with pytest.raises(ADAPTER_ERROR[0], match=MED_FULL):
        _fetch(adapter, [MED_FULL])


def test_fetch_raises_when_only_another_collection_answers(adapter, fake_epmc):
    fake_epmc.records = [{**core_record("MED", "99000001"), "source": "CTX"}]

    with pytest.raises(ADAPTER_ERROR[0], match=MED_FULL):
        _fetch(adapter, [MED_FULL])


def test_fetch_missing_record_error_stays_bounded(adapter, fake_epmc):
    template = core_record("MED", "99000002")
    fake_epmc.records = [{**template, "id": str(97000000 + i)} for i in range(0, 150, 5)]
    ids = [f"MED:{97000000 + i}" for i in range(150)]

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]) as excinfo:
        _fetch(adapter, ids)

    message = str(excinfo.value)
    assert "MED:97000001" in message
    assert len(message) < 1000


def test_fetch_collapses_duplicate_hits_and_out_of_order_results(adapter, fake_epmc):
    fake_epmc.unrequested_extras = [core_record("MED", "99000001")]

    records = _fetch(adapter, [PMC_ONLY, MED_MINIMAL, MED_FULL, PPR])

    assert sorted(r.source_id for r in records) == sorted(ALL_FIXTURE_IDS)


def test_fetch_tolerates_duplicate_requested_ids(adapter, fake_epmc):
    records = _fetch(adapter, [MED_FULL, MED_FULL])

    assert [r.source_id for r in records] == [MED_FULL]


def test_fetch_skips_incomplete_items_without_losing_valid_records(adapter, fake_epmc):
    valid = core_record("MED", "99000001")
    fake_epmc.core_payload = {
        "hitCount": 5,
        "resultList": {"result": [None, 7, "x", {"title": "no id or source"}, valid]},
    }

    assert [r.source_id for r in _fetch(adapter, [MED_FULL])] == [MED_FULL]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"hitCount": 1},
        {"hitCount": 1, "resultList": None},
        {"hitCount": 1, "resultList": {}},
        {"hitCount": 1, "resultList": {"result": None}},
        {"hitCount": 1, "resultList": {"result": "unexpected"}},
        [],
        {"errCode": 500, "errMsg": "Internal error"},
    ],
    ids=["empty", "no-result-list", "null-result-list", "no-result", "null-result", "string-result",
         "top-level-array", "err-payload"],
)
def test_fetch_rejects_invalid_or_error_envelopes(adapter, fake_epmc, payload):
    fake_epmc.core_payload = copy.deepcopy(payload)

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _fetch(adapter, [MED_FULL])


def test_fetch_raises_on_invalid_json(adapter, fake_epmc):
    fake_epmc.raw_body = "not json"

    with pytest.raises(ADAPTER_ERROR[0], match=ADAPTER_ERROR[1]):
        _fetch(adapter, [MED_FULL])


def test_fetch_http_error_propagates(adapter, fake_epmc):
    fake_epmc.status_code = 500

    with pytest.raises(httpx.HTTPStatusError):
        _fetch(adapter, [MED_FULL])


# ---------------------------------------------------------------------------
# B. Record mapping
# ---------------------------------------------------------------------------

def test_med_record_maps_identifiers_and_bibliographic_fields(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, core_record("MED", "99000001"))

    assert r.source_id == MED_FULL
    assert r.source_database == "europepmc"
    assert r.doi == "10.5555/bibmeded.epmc.0001"
    assert r.external_ids["doi"] == "10.5555/bibmeded.epmc.0001"
    assert r.external_ids["pmid"] == "99000001"
    assert r.external_ids["pmcid"] == "PMC99000001"
    assert r.title.startswith("Simulation-based training")
    assert r.abstract == "Synthetic abstract describing a simulation curriculum."
    assert r.year == 2023
    assert r.journal_name == "Journal of Synthetic Medical Education"
    assert r.journal_issn == "1234-5678"
    assert r.publication_type == "Journal Article"
    assert r.references == []


def test_ppr_preprint_without_pmid_and_normalised_doi(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, core_record("PPR", "PPR990001"))

    assert r.source_id == PPR
    assert "pmid" not in r.external_ids
    assert "pmcid" not in r.external_ids
    assert r.doi == "10.5555/preprint.epmc.0002"
    assert r.external_ids["doi"] == r.doi
    assert r.year == 2024
    assert r.publication_type == "Preprint"


def test_pmc_only_record_keeps_pmcid_without_inventing_pmid(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, core_record("PMC", "PMC99000009"))

    assert r.source_id == PMC_ONLY
    assert r.external_ids["pmcid"] == "PMC99000009"
    assert "pmid" not in r.external_ids
    assert r.doi == "10.5555/pmc.only.0009"
    assert r.year == 2022
    assert r.journal_name == "Synthetic Open Journal"
    assert r.journal_issn == "1111-2222"


@pytest.mark.parametrize("source,record_id", [("PPR", "PPR990031"), ("PMC", "PMC99000032"), ("AGR", "AGR990033")])
def test_valid_pmid_is_kept_whatever_the_source_collection(adapter, fake_epmc, source, record_id):
    r = _fetch_one(adapter, fake_epmc, {"id": record_id, "source": source, "title": "t", "pmid": "99000030"})

    assert r.external_ids["pmid"] == "99000030"


def test_med_id_is_the_pmid_when_the_pmid_field_is_absent(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000034", "source": "MED", "title": "t"})

    assert r.external_ids["pmid"] == "99000034"


def test_pmc_id_is_the_pmcid_when_the_pmcid_field_is_absent(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, {"id": "PMC99000035", "source": "PMC", "title": "t"})

    assert r.external_ids["pmcid"] == "PMC99000035"


def test_med_and_ppr_with_same_number_are_distinct_records(adapter, fake_epmc):
    med = {"id": "12345", "source": "MED", "pmid": "12345", "title": "MED twin"}
    ppr = {"id": "12345", "source": "PPR", "title": "PPR twin"}
    fake_epmc.records = [med, ppr]

    records = _by_source_id(_fetch(adapter, ["MED:12345", "PPR:12345"]))

    assert set(records) == {"MED:12345", "PPR:12345"}
    assert records["MED:12345"].external_ids.get("pmid") == "12345"
    assert "pmid" not in records["PPR:12345"].external_ids


@pytest.mark.parametrize(
    "raw_doi",
    [
        "10.5555/ABC.Def",
        "https://doi.org/10.5555/ABC.Def",
        "http://doi.org/10.5555/ABC.Def",
        "doi:10.5555/ABC.Def",
        "  10.5555/ABC.Def  ",
    ],
)
def test_doi_is_lowercased_and_unprefixed(adapter, fake_epmc, raw_doi):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000010", "source": "MED", "title": "t", "doi": raw_doi})

    assert r.doi == "10.5555/abc.def"
    assert r.external_ids["doi"] == "10.5555/abc.def"


@pytest.mark.parametrize("raw_doi", [None, "", "   "])
def test_blank_doi_is_absent(adapter, fake_epmc, raw_doi):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000011", "source": "MED", "title": "t", "doi": raw_doi})

    assert r.doi is None
    assert "doi" not in r.external_ids


@pytest.mark.parametrize("raw_pmid,expected", [("99000012", "99000012"), (" 99000012 ", "99000012"),
                                               (99000012, "99000012"), ("not-a-pmid", None),
                                               ("", None), (None, None)])
def test_pmid_field_is_bare_numeric_or_absent(adapter, fake_epmc, raw_pmid, expected):
    r = _fetch_one(adapter, fake_epmc, {"id": "PPR990012", "source": "PPR", "title": "t", "pmid": raw_pmid})

    assert r.external_ids.get("pmid") == expected


@pytest.mark.parametrize("raw_pmcid,expected", [("PMC99000013", "PMC99000013"), ("pmc99000013", "PMC99000013"),
                                                (" PMC99000013 ", "PMC99000013"), ("PMCX", None),
                                                ("", None), (None, None)])
def test_pmcid_is_normalised_or_absent(adapter, fake_epmc, raw_pmcid, expected):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000013", "source": "MED", "title": "t", "pmcid": raw_pmcid})

    assert r.external_ids.get("pmcid") == expected


def test_authors_orcid_and_affiliations(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, core_record("MED", "99000001"))

    assert [a.name for a in r.authors] == ["Example J", "Sample A", "BibMedEd Synthetic Consortium"]
    first, second, collective = r.authors
    assert first.orcid == "0000-0002-1825-0097"
    assert first.affiliation == "Department of Medical Education, Synthetic University Hospital, Ankara, Turkey."
    assert second.orcid is None
    assert second.affiliation is None
    assert collective.orcid is None


def test_orcid_url_form_is_stripped(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, core_record("PPR", "PPR990001"))

    assert r.authors[0].orcid == "0000-0002-1694-233X"
    assert r.authors[0].affiliation == "Synthetic Preprint Lab, Toronto, Canada."


def test_mesh_terms_and_keywords(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, core_record("MED", "99000001"))

    assert r.mesh_terms == ["Education, Medical, Undergraduate", "Humans"]
    assert r.keywords == ["simulation", "curriculum"]


def test_missing_optional_fields_map_to_safe_empties(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, core_record("MED", "99000002"))

    assert r.source_id == MED_MINIMAL
    assert r.title == "Minimal synthetic MEDLINE record"
    assert r.abstract is None
    assert r.doi is None
    assert r.year is None
    assert r.journal_name is None
    assert r.journal_issn is None
    assert r.publication_type is None
    assert r.authors == []
    assert r.mesh_terms == []
    assert r.keywords == []
    assert r.references == []
    assert {k: v for k, v in r.external_ids.items() if k != "europepmc"} == {"pmid": "99000002"}


def test_null_nested_containers_do_not_crash(adapter, fake_epmc):
    record = {
        "id": "99000014", "source": "MED", "title": "nulls",
        "authorList": None, "journalInfo": None, "meshHeadingList": None,
        "keywordList": None, "pubTypeList": None, "bookOrReportDetails": None,
    }

    r = _fetch_one(adapter, fake_epmc, record)

    assert r.authors == [] and r.mesh_terms == [] and r.keywords == []
    assert r.journal_name is None and r.publication_type is None


def test_year_falls_back_to_journal_year_and_ignores_garbage(adapter, fake_epmc):
    fallback = _fetch_one(adapter, fake_epmc, {
        "id": "99000015", "source": "MED", "title": "t",
        "journalInfo": {"yearOfPublication": 2019},
    })
    garbage = _fetch_one(adapter, fake_epmc, {"id": "99000016", "source": "MED", "title": "t", "pubYear": "n.d."})

    assert fallback.year == 2019
    assert garbage.year is None


def test_missing_title_becomes_empty_string(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000017", "source": "MED"})

    assert r.title == ""


SYNTHETIC_HTML_ABSTRACT = (
    "<h4>Background</h4><p>Synthetic background sentence about <i>simulation</i>"
    " training.</p>\n<h4>Methods</h4><p>Synthetic cohort of 42&nbsp;students;"
    " H<sub>2</sub>O &amp; saline<br/>second line &lt;placebo&gt;.</p>"
    "<h4>Results</h4>Synthetic effect &#946;&nbsp;=&nbsp;0.31 (p<0.05).<p></p>"
)
SYNTHETIC_PLAIN_ABSTRACT = (
    "Background: synthetic sentence.\nMethods: synthetic cohort, p < 0.05; dose >= 2 mg."
)


def test_html_abstract_is_flattened_to_plain_text_sections(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, {
        "id": "99000018", "source": "MED", "title": "t", "abstractText": SYNTHETIC_HTML_ABSTRACT,
    })

    assert r.abstract == (
        "Background\n"
        "Synthetic background sentence about simulation training.\n"
        "Methods\n"
        "Synthetic cohort of 42 students; H2O & saline\n"
        "second line <placebo>.\n"
        "Results\n"
        "Synthetic effect β = 0.31 (p<0.05)."
    )


@pytest.mark.parametrize("plain", [
    SYNTHETIC_PLAIN_ABSTRACT,
    "R&D-funded synthetic study; ratio 3<4 and 5 > 2.",
])
def test_plain_text_abstract_is_kept_unchanged(adapter, fake_epmc, plain):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000019", "source": "MED", "title": "t", "abstractText": plain})

    assert r.abstract == plain


def test_unterminated_tag_at_end_of_html_abstract_is_kept_as_text(adapter, fake_epmc):
    r = _fetch_one(adapter, fake_epmc, {
        "id": "99000021", "source": "MED", "title": "t",
        "abstractText": "<h4>Results</h4><p>Synthetic ratio a &amp; n<b",
    })

    assert r.abstract == "Results\nSynthetic ratio a & n<b"


@pytest.mark.parametrize(("abstract", "expected"), [
    pytest.param("<custom>Important result</custom>", "Important result", id="custom-tag-only"),
    pytest.param("Synthetic<custom>boundary</custom>text", "Synthetic boundary text", id="custom-tag-no-glue"),
    pytest.param("<p>Synthetic before<custom-break/>after<x-marker /></p>", "Synthetic before after",
                 id="unknown-self-closing"),
    pytest.param("<script>alert(1)</script>", None, id="script-only"),
    pytest.param("<p>Synthetic before.</p><script>var x = '<p>leak</p>'; alert(x);</script><p>Synthetic after.</p>",
                 "Synthetic before.\nSynthetic after.", id="script-between-paragraphs"),
    pytest.param("Synthetic before <style>p { color: red; } h4::after { content: '<b>'; }</style>after.",
                 "Synthetic before after.", id="style-inline"),
    pytest.param("<div><SCRIPT type='text/javascript'>document.write('x')</SCRIPT>Synthetic kept"
                 "<style>.a{}</style><script>b()</script> text.</div>",
                 "Synthetic kept text.", id="script-and-style-nested-in-block"),
    pytest.param("<p>Synthetic effect p<0.05, β=0.05, n>=30 and H<sub>2</sub>O.</p>",
                 "Synthetic effect p<0.05, β=0.05, n>=30 and H2O.", id="scientific-comparators"),
    pytest.param("<p>Synthetic arm &lt;placebo&gt; vs &lt;drug&gt; &amp; control.</p>",
                 "Synthetic arm <placebo> vs <drug> & control.", id="encoded-angle-brackets"),
    pytest.param("<h4>Background</h4><p>Synthetic one.</p><h4>Methods</h4><p>Synthetic two.<br>Line three.</p>",
                 "Background\nSynthetic one.\nMethods\nSynthetic two.\nLine three.", id="structured"),
    pytest.param("<h4>Results<p>Synthetic effect p<0.05; n=12</i> and β=0.05</custom><p>Synthetic next",
                 "Results\nSynthetic effect p<0.05; n=12 and β=0.05\nSynthetic next", id="malformed"),
])
def test_html_abstract_markup_cases(adapter, fake_epmc, abstract, expected):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000022", "source": "MED", "title": "t", "abstractText": abstract})

    assert r.abstract == expected


@pytest.mark.parametrize("markup", ["<p> </p>", "<h4></h4><br>", "&nbsp;"])
def test_markup_only_abstract_is_absent(adapter, fake_epmc, markup):
    r = _fetch_one(adapter, fake_epmc, {"id": "99000020", "source": "MED", "title": "t", "abstractText": markup})

    assert r.abstract is None


# ---------------------------------------------------------------------------
# Captured Europe PMC payloads (see fixtures/europepmc_real_PROVENANCE.md)
# ---------------------------------------------------------------------------

def test_real_idlist_page_parses(adapter, fake_epmc):
    fake_epmc.pages = {"*": load_fixture("europepmc_real_idlist_page.json")}

    result = asyncio.run(adapter.search("q"))

    assert result.total_count == 26
    assert result.ids == ["MED:34093275", "MED:33086367", "MED:34222746", "MED:34826270", "MED:34011088"]


def test_real_core_records_map_identifiers_and_metadata(adapter, fake_epmc):
    fake_epmc.records = load_fixture("europepmc_real_core_topic.json")["resultList"]["result"]
    ids = ["MED:34093275", "MED:33086367", "MED:34222746", "MED:34826270", "MED:34011088"]

    records = _by_source_id(_fetch(adapter, ids))

    assert set(records) == set(ids)
    sim = records["MED:33086367"]
    assert sim.external_ids["pmid"] == "33086367"
    assert sim.external_ids["pmcid"] == "PMC8580374"
    assert sim.doi == "10.1097/sih.0000000000000509"
    assert sim.year == 2021
    assert sim.publication_type == "research-article"
    assert sim.journal_name.startswith("Simulation in healthcare")
    assert len(sim.mesh_terms) == 6
    assert len(sim.authors) == 5
    review = records["MED:34093275"]
    assert len(review.keywords) == 5
    assert sum(1 for a in review.authors if a.orcid) == 2
    assert "pmcid" not in records["MED:34826270"].external_ids
    assert all(re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", a.orcid)
               for r in records.values() for a in r.authors if a.orcid)
    assert sim.abstract.split("\n")[::2] == ["Introduction", "Methods", "Results", "Conclusions"]
    assert all("<" not in r.abstract and ">" not in r.abstract for r in records.values() if r.abstract)


def test_real_records_from_every_documented_collection_are_fetchable(adapter, fake_epmc):
    fake_epmc.records = load_fixture("europepmc_real_core_collections.json")["resultList"]["result"]
    ids = [f"{s}:{i}" for s, i in DOCUMENTED_COLLECTIONS]

    records = _by_source_id(_fetch(adapter, ids))

    assert set(records) == set(ids)
    assert records["MED:42954961"].external_ids["pmid"] == "42954961"
    assert records["PMC:PMC13787573"].external_ids["pmcid"] == "PMC13787573"
    assert records["PPR:PPR1373820"].doi == "10.64898/2026.11.20.767967"
    assert records["PPR:PPR1373820"].publication_type == "Preprint"
    assert records["NBK:NBK623779"].publication_type == "Book"
    assert all("pmid" not in r.external_ids for k, r in records.items() if k != "MED:42954961")
    assert records["MED:42954961"].abstract.split("\n")[:2] == [
        "Introduction",
        "Synthetic placeholder sentence for the Introduction section. Synthetic statistic (\u03b2=0.05; p<0.05).",
    ]


def test_captured_fixtures_decode_as_utf8_whatever_the_platform_default(adapter, fake_epmc, monkeypatch):
    read_text = Path.read_text

    def read_text_with_windows_default(self, encoding=None, *args, **kwargs):
        return read_text(self, encoding or "cp1252", *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text_with_windows_default)
    fake_epmc.records = load_fixture("europepmc_real_core_collections.json")["resultList"]["result"]

    med = _fetch(adapter, ["MED:42954961"])[0]

    assert med.authors[0].name == "Synthetic Author \u00dcnal-\u00c7elik (MED:42954961)"
    assert "\u03b2=0.05; p<0.05" in med.abstract


def test_close_closes_every_http_client(adapter_cls, fake_epmc, tracked_clients):
    instance = adapter_cls()
    asyncio.run(instance.search("medical education"))
    asyncio.run(instance.fetch([MED_FULL]))

    asyncio.run(instance.close())

    assert tracked_clients, "adapter is expected to use httpx.AsyncClient"
    assert all(client.is_closed for client in tracked_clients)
