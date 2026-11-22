"""Integration tests for the Europe PMC adapter (issue #7): registry
discovery, search schema, the paginated worker flow, identifier persistence, and
the existing DOI/PMID-only cross-source deduplication.

Network traffic is served by ``tests/europepmc_fake.py``; nothing reaches Europe PMC.
"""

import asyncio
import re
import typing
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from bibmeded.adapters.base import RawAuthor, RawRecord
from bibmeded.adapters.europepmc import EuropePMCAdapter
from bibmeded.adapters.registry import discover_adapters, get_adapter, list_adapters
from bibmeded.adapters.settings import adapter_configuration_error
from bibmeded.models import MethodologyStep, Publication, QueryStatus, SearchProject, SearchQuery
from bibmeded.schemas.search import AdapterSource, SearchRequest
from bibmeded.services.cleaning import deduplicate_cross_source
from bibmeded.workers import tasks
from tests.europepmc_fake import (  # noqa: F401 — pytest fixtures
    fake_epmc,
    tracked_clients,
)

pytestmark = pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning")


def _fetch_records(ids: list[str]) -> list[RawRecord]:
    adapter = EuropePMCAdapter()

    async def run():
        try:
            return await adapter.fetch(ids)
        finally:
            await adapter.close()

    return asyncio.run(run())


def _one(ids: str) -> RawRecord:
    records = _fetch_records([ids])
    assert len(records) == 1
    return records[0]


def _make_query(db, database: str = "europepmc") -> SearchQuery:
    project = SearchProject(name="Europe PMC project")
    db.add(project)
    db.commit()
    query = SearchQuery(project_id=project.id, query_string="medical education",
                        database=database, status=QueryStatus.pending)
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


class _StubTask:
    def update_state(self, *args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Registry, settings and search schema
# ---------------------------------------------------------------------------

def test_registry_auto_discovers_europepmc():
    discover_adapters()
    adapters = {a["name"]: a for a in list_adapters()}

    assert "europepmc" in adapters, "RED: registry did not discover a 'europepmc' adapter"
    assert adapters["europepmc"] == {
        "name": "europepmc", "display_name": "Europe PMC", "requires_api_key": False,
    }


def test_worker_settings_build_europepmc_without_configuration(fake_epmc):
    discover_adapters()

    assert adapter_configuration_error("europepmc") is None
    adapter = get_adapter("europepmc", **tasks._adapter_kwargs("europepmc"))
    try:
        assert adapter.name == "europepmc"
    finally:
        asyncio.run(adapter.close())


def test_search_schema_accepts_europepmc():
    assert "europepmc" in typing.get_args(AdapterSource), "RED: AdapterSource lacks 'europepmc'"
    assert SearchRequest(query_string="medical education", source="europepmc").source == "europepmc"


def test_search_schema_still_rejects_unknown_sources():
    with pytest.raises(ValidationError):
        SearchRequest(query_string="medical education", source="europe_pmc")


def test_search_route_dispatches_europepmc(client, db):
    project = SearchProject(name="Europe PMC route")
    db.add(project)
    db.commit()
    db.refresh(project)

    with patch("bibmeded.routers.search.run_search") as mock_task:
        response = client.post(
            f"/api/projects/{project.id}/search",
            json={"query_string": "medical education", "source": "europepmc",
                  "year_start": "2020", "year_end": "2024"},
        )

    assert response.status_code == 202, f"RED: route rejected europepmc: {response.text}"
    assert mock_task.delay.call_args.args[1] == "europepmc"


# ---------------------------------------------------------------------------
# Worker: paginated search, cap, fetch, persistence, methodology
# ---------------------------------------------------------------------------

@pytest.fixture
def task_session_factory(db):
    return sessionmaker(bind=db.connection())


def test_run_search_end_to_end_caps_results_and_preserves_upstream_total(
    db, monkeypatch, task_session_factory, fake_epmc, tracked_clients
):
    discover_adapters()
    query = _make_query(db)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)

    asyncio.run(tasks._run_search(_StubTask(), query.id, "europepmc", "2020", "2024", 4))

    db.expire_all()
    stored = db.get(SearchQuery, query.id)
    assert stored.status == QueryStatus.completed
    assert stored.raw_result_count == 5000
    assert stored.result_count == 4

    cursors = [r.params.get("cursorMark", "*") for r in fake_epmc.search_requests]
    assert cursors == ["*", "AoIIP0SYNTH01"], "worker stops paging once max_results is reached"
    assert "PUB_YEAR" in fake_epmc.search_requests[0].query.upper()
    assert len(fake_epmc.core_requests) == 1

    search_step = db.query(MethodologyStep).filter_by(query_id=query.id, phase="search").one()
    assert search_step.action == "Europe PMC API search"
    assert search_step.parameters["upstream_total"] == 5000
    assert search_step.parameters["capped"] is True
    assert search_step.parameters["retrieved_ids"] == 4
    assert search_step.parameters["year_filters"] == {"year_start": "2020", "year_end": "2024"}

    pubs = {p.source_id: p for p in db.query(Publication).filter_by(query_id=query.id)}
    assert set(pubs) == {"MED:99000001", "PPR:PPR990001", "MED:99000002", "PMC:PMC99000009"}
    assert all(p.source_database == "europepmc" for p in pubs.values())

    med = pubs["MED:99000001"]
    assert med.pmid == "99000001"
    assert med.doi == "10.5555/bibmeded.epmc.0001"
    assert med.external_ids["europepmc"] == "MED:99000001"
    assert med.external_ids["pmcid"] == "PMC99000001"

    preprint = pubs["PPR:PPR990001"]
    assert preprint.pmid is None
    assert preprint.doi == "10.5555/preprint.epmc.0002"
    assert preprint.external_ids["europepmc"] == "PPR:PPR990001"

    pmc_only = pubs["PMC:PMC99000009"]
    assert pmc_only.pmid is None
    assert pmc_only.external_ids["pmcid"] == "PMC99000009"

    assert tracked_clients and all(c.is_closed for c in tracked_clients)


def test_html_abstract_reaches_ris_export_as_plain_text_sections(
    client, db, monkeypatch, task_session_factory, fake_epmc
):
    discover_adapters()
    query = _make_query(db)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    fake_epmc.pages = {"*": {"hitCount": 1, "resultList": {"result": [{"id": "99000030", "source": "MED"}]}}}
    fake_epmc.records = [{
        "id": "99000030", "source": "MED", "title": "Synthetic structured abstract",
        "abstractText": (
            "<h4>Background</h4><p>Synthetic background sentence.</p>"
            "<h4>Methods</h4><p>Synthetic <i>methods</i> sentence &amp; H<sub>2</sub>O"
            "<custom-note>with custom</custom-note>tag &lt;placebo&gt;.</p>"
            "<script>document.write('<p>injected</p>'); alert(1);</script>"
            "<style>p { color: red; }</style>"
            "<h4>Results</h4>Synthetic result, p<0.05.<x-marker/><br>Second synthetic line."
        ),
    }]

    asyncio.run(tasks._run_search(_StubTask(), query.id, "europepmc", None, None, 10))
    ris = client.get(f"/api/projects/{query.project_id}/export/ris")

    assert ris.status_code == 200
    abstract_lines = [line for line in ris.text.split("\n") if line.startswith("AB  - ")]
    assert abstract_lines == [
        "AB  - Background Synthetic background sentence. Methods Synthetic methods sentence & H2O"
        " with custom tag <placebo>. Results Synthetic result, p<0.05. Second synthetic line."
    ]
    tags = re.findall(r"</?[a-zA-Z][^>]*>|&[a-zA-Z#]\w*;", abstract_lines[0])
    assert tags == ["<placebo>"], "only the entity-encoded literal may look like a tag"
    for leaked in ("custom-note", "x-marker", "script", "document.write", "injected", "alert", "style", "color"):
        assert leaked not in abstract_lines[0]


@pytest.mark.parametrize(
    "first_page",
    [
        {"errCode": 503, "errMsg": "Search service unavailable"},
        {"version": "6.9"},
        {"hitCount": 50, "nextCursorMark": "*", "resultList": {"result": [{"id": "99000001", "source": "MED"}]}},
        {"hitCount": 50, "resultList": {"result": []}},
        {"hitCount": 2, "resultList": {"result": [{"id": "99000001", "source": "MED"}] * 2}},
        {"hitCount": 1, "resultList": {"result": [{"id": "1", "source": "XYZ"}]}},
    ],
    ids=["api-error-payload", "malformed-envelope", "cursor-ends-before-hit-count",
         "empty-page-before-hit-count", "duplicate-ids", "unknown-collection"],
)
def test_run_search_marks_upstream_failure_as_failed_not_empty(
    db, monkeypatch, task_session_factory, fake_epmc, first_page
):
    discover_adapters()
    query = _make_query(db)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    fake_epmc.pages = {"*": first_page}

    with pytest.raises(RuntimeError, match="Europe PMC"):
        asyncio.run(tasks._run_search(_StubTask(), query.id, "europepmc", None, None, 100))

    db.expire_all()
    stored = db.get(SearchQuery, query.id)
    assert stored.status == QueryStatus.failed
    assert stored.result_count is None
    assert db.query(Publication).filter_by(query_id=query.id).count() == 0


def test_run_search_incomplete_fetch_fails_but_keeps_previously_committed_batches(
    db, monkeypatch, task_session_factory, fake_epmc
):
    """The worker commits each fetch batch (``_persist_records(commit=True)``), so a
    later incomplete batch fails the query without rolling back earlier batches.
    This pins that pre-existing worker behaviour for Europe PMC; it is not partial
    success: the query ends ``failed`` with no result_count and no fetch step."""
    discover_adapters()
    query = _make_query(db)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    monkeypatch.setattr(tasks, "FETCH_BATCH_SIZE", 2)
    fake_epmc.pages = {"*": {"hitCount": 4, "resultList": {"result": [
        {"id": "99000001", "source": "MED"}, {"id": "PPR990001", "source": "PPR"},
        {"id": "99000002", "source": "MED"}, {"id": "PMC99000009", "source": "PMC"},
    ]}}}
    fake_epmc.records = [r for r in fake_epmc.records if r["id"] != "PMC99000009"]

    with pytest.raises(RuntimeError, match="PMC:PMC99000009"):
        asyncio.run(tasks._run_search(_StubTask(), query.id, "europepmc", None, None, 100))

    db.expire_all()
    stored = db.get(SearchQuery, query.id)
    assert stored.status == QueryStatus.failed
    assert stored.result_count is None
    persisted = {p.source_id for p in db.query(Publication).filter_by(query_id=query.id)}
    assert persisted == {"MED:99000001", "PPR:PPR990001"}
    phases = {s.phase for s in db.query(MethodologyStep).filter_by(query_id=query.id)}
    assert "fetch" not in phases


def test_rerunning_same_europepmc_record_does_not_duplicate(db, fake_epmc):
    query = _make_query(db)
    record = _one("MED:99000001")

    assert tasks._persist_records(db, [record], query.id, query.project_id).persisted == 1
    assert tasks._persist_records(db, [record], query.id, query.project_id).persisted == 0


def _pubmed_record(pmid: str, doi: str | None = None) -> RawRecord:
    external_ids = {"pmid": pmid, **({"doi": doi} if doi else {})}
    return RawRecord(source_id=pmid, source_database="pubmed", title="PubMed twin", doi=doi,
                     authors=[RawAuthor(name="Twin A")], mesh_terms=["Humans"], external_ids=external_ids)


def test_pubmed_first_then_europepmc_merges_identifiers(db, fake_epmc):
    query = _make_query(db)
    europepmc = _one("MED:99000001")

    tasks._persist_records(db, [_pubmed_record("99000001")], query.id, query.project_id)
    assert tasks._persist_records(db, [europepmc], query.id, query.project_id).persisted == 0

    pub = db.query(Publication).filter_by(project_id=query.project_id).one()
    assert pub.source_database == "pubmed"
    assert pub.external_ids["europepmc"] == "MED:99000001"
    assert pub.external_ids["pmcid"] == "PMC99000001"


# ---------------------------------------------------------------------------
# Existing cross-source dedup: DOI and PMID only, PMCID deliberately out of scope
# ---------------------------------------------------------------------------

def test_cross_source_dedup_matches_europepmc_by_pmid(fake_epmc):
    europepmc = _one("MED:99000001")

    unique, removed, by_field = deduplicate_cross_source([_pubmed_record("99000001"), europepmc])

    assert removed == 1
    assert by_field == {"doi": 0, "pmid": 1}
    assert unique[0].source_database == "pubmed"


def test_cross_source_dedup_matches_preprint_by_doi_across_case_and_prefix(fake_epmc):
    preprint = _one("PPR:PPR990001")
    openalex = RawRecord(
        source_id="W990001", source_database="openalex", title="OpenAlex twin",
        doi="https://doi.org/10.5555/PREPRINT.EPMC.0002",
        external_ids={"openalex": "W990001", "doi": "https://doi.org/10.5555/PREPRINT.EPMC.0002"},
    )

    unique, removed, by_field = deduplicate_cross_source([openalex, preprint])

    assert removed == 1
    assert by_field == {"doi": 1, "pmid": 0}


def test_cross_source_dedup_does_not_match_on_pmcid_alone(fake_epmc):
    pmc_only = _one("PMC:PMC99000009")
    other = RawRecord(source_id="X1", source_database="openalex", title="PMCID-only twin",
                      external_ids={"pmcid": "PMC99000009"})

    unique, removed, by_field = deduplicate_cross_source([pmc_only, other])

    assert removed == 0
    assert set(by_field) == {"doi", "pmid"}
    assert len(unique) == 2
