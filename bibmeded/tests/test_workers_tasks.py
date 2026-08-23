import asyncio
import logging

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.adapters.base import RawAuthor, RawRecord
from app.adapters.registry import discover_adapters, get_adapter
from app.config import settings
from app.models import (
    MethodologyStep,
    Publication,
    QueryStatus,
    SearchProject,
    SearchQuery,
)
from app.workers import tasks


def _make_record(
    pmid: str,
    *,
    doi: str | None = None,
    affiliation: str | None = "Some Hospital, USA",
    title: str = "A Study",
) -> RawRecord:
    external_ids = {"pmid": pmid}
    if doi:
        external_ids["doi"] = doi
    return RawRecord(
        source_id=pmid,
        source_database="pubmed",
        title=title,
        abstract="Abstract text",
        doi=doi,
        year=2024,
        journal_name="Journal of Testing",
        authors=[RawAuthor(name=f"Author {pmid}", affiliation=affiliation)],
        mesh_terms=["Education"],
        keywords=["medical education"],
        external_ids=external_ids,
    )


def _make_query(db, project_name: str = "Test project") -> SearchQuery:
    project = SearchProject(name=project_name)
    db.add(project)
    db.commit()
    db.refresh(project)
    query = SearchQuery(
        project_id=project.id,
        query_string="test query",
        database="pubmed",
        status=QueryStatus.pending,
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


def _make_openalex_record(
    source_id: str, *, pmid: str | None = None, doi: str | None = None, title: str = "A Study"
) -> RawRecord:
    """An OpenAlex-shaped record whose primary id (source_id) is a W-id, not a PMID.
    Any real PMID it carries lives in external_ids['pmid'] per the RawRecord contract."""
    external_ids: dict[str, str] = {}
    if pmid:
        external_ids["pmid"] = pmid
    if doi:
        external_ids["doi"] = doi
    return RawRecord(
        source_id=source_id,
        source_database="openalex",
        title=title,
        abstract="Abstract text",
        doi=doi,
        year=2024,
        journal_name="Journal of Testing",
        authors=[RawAuthor(name=f"Author {source_id}", affiliation="Some Hospital, USA")],
        mesh_terms=[],
        keywords=["medical education"],
        external_ids=external_ids,
    )


class _StubTask:
    """Minimal stand-in for the Celery bound task object (`self`) — only
    `update_state` is ever called on it by `_run_search`."""

    def update_state(self, *args, **kwargs):
        pass


class _StubAdapter:
    """Minimal adapter double: yields a fixed id batch, then fetches the
    matching RawRecords for those ids. No network I/O."""

    def __init__(self, ids: list[str], records: list[RawRecord]):
        self._ids = ids
        self._records = records
        self.closed = False

    async def search_paginated(self, query, **kwargs):
        yield self._ids

    async def fetch_stream(self, ids, batch_size=200):
        yield [r for r in self._records if r.source_id in ids]

    def methodology_label(self) -> str:
        return "Stub API"

    async def close(self) -> None:
        self.closed = True


class _FailingICiteClient:
    def __init__(self, exc: Exception):
        self._exc = exc
        self.closed = False

    async def get_citations(self, pmids):
        raise self._exc

    async def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# (c) _persist_records — persist basics + per-record savepoint isolation
# ---------------------------------------------------------------------------

def test_persist_records_persists_valid_records_with_relations(db):
    query = _make_query(db)
    records = [_make_record("1001"), _make_record("1002")]

    count, pmids = tasks._persist_records(db, records, query.id, query.project_id)

    assert count == 2
    assert sorted(pmids) == ["1001", "1002"]
    pubs = db.query(Publication).filter(Publication.query_id == query.id).all()
    assert len(pubs) == 2
    for pub in pubs:
        assert pub.journal_id is not None
        assert len(pub.authors) == 1
        assert len(pub.keywords) == 2  # one mesh term + one author keyword


def test_persist_records_returns_zero_for_empty_batch(db):
    query = _make_query(db)

    count, pmids = tasks._persist_records(db, [], query.id, query.project_id)

    assert count == 0
    assert pmids == []


def test_persist_records_rolls_back_single_bad_record_others_still_persist(db, monkeypatch):
    query = _make_query(db)
    records = [
        _make_record("2001", affiliation="Good Hospital, USA"),
        _make_record("2002", affiliation="TRIGGER_FAIL"),
        _make_record("2003", affiliation="Another Hospital, USA"),
    ]

    real_extract_country = tasks.extract_country

    def flaky_extract_country(affiliation):
        if affiliation == "TRIGGER_FAIL":
            raise ValueError("simulated per-record failure")
        return real_extract_country(affiliation)

    monkeypatch.setattr(tasks, "extract_country", flaky_extract_country)

    count, pmids = tasks._persist_records(db, records, query.id, query.project_id)

    assert count == 2
    assert sorted(pmids) == ["2001", "2003"]
    pubs = db.query(Publication).filter(Publication.query_id == query.id).all()
    assert sorted(p.pmid for p in pubs) == ["2001", "2003"]
    assert db.query(Publication).filter(Publication.pmid == "2002").first() is None


# ---------------------------------------------------------------------------
# (b) Adapter courtesy/rate-limit settings wiring
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_adapters_discovered():
    discover_adapters()


def test_adapter_kwargs_unknown_source_returns_empty_dict():
    assert tasks._adapter_kwargs("not-a-real-source") == {}


def test_adapter_kwargs_pubmed_reflects_configured_api_key_and_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "pubmed_api_key", "pm-key-123")
    monkeypatch.setattr(settings, "pubmed_rate_limit", 9.5)

    kwargs = tasks._adapter_kwargs("pubmed")

    assert kwargs == {"api_key": "pm-key-123", "rate_limit": 9.5}


def test_adapter_kwargs_openalex_reflects_configured_email(monkeypatch):
    monkeypatch.setattr(settings, "openalex_email", "team@example.org")

    assert tasks._adapter_kwargs("openalex") == {"email": "team@example.org"}


def test_adapter_kwargs_crossref_reflects_configured_email(monkeypatch):
    monkeypatch.setattr(settings, "crossref_email", "team@example.org")

    assert tasks._adapter_kwargs("crossref") == {"email": "team@example.org"}


def test_adapter_kwargs_semantic_scholar_reflects_configured_api_key(monkeypatch):
    monkeypatch.setattr(settings, "semantic_scholar_api_key", "s2-secret")

    assert tasks._adapter_kwargs("semanticscholar") == {"api_key": "s2-secret"}


def test_adapter_kwargs_lens_reflects_configured_api_key(monkeypatch):
    test_value = "lens-" + "test-token"
    monkeypatch.setattr(settings, "lens_api_key", test_value, raising=False)

    assert tasks._adapter_kwargs("lens") == {"api_key": test_value}


def test_get_adapter_with_settings_wires_pubmed_api_key_and_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "pubmed_api_key", "pm-key-abc")
    monkeypatch.setattr(settings, "pubmed_rate_limit", 7.0)

    adapter = get_adapter("pubmed", **tasks._adapter_kwargs("pubmed"))

    assert adapter._client.api_key == "pm-key-abc"
    assert adapter._client.rate_limit == 7.0


def test_get_adapter_with_settings_wires_openalex_email(monkeypatch):
    monkeypatch.setattr(settings, "openalex_email", "researcher@example.org")

    adapter = get_adapter("openalex", **tasks._adapter_kwargs("openalex"))

    assert adapter._email == "researcher@example.org"


def test_get_adapter_with_settings_wires_crossref_email(monkeypatch):
    monkeypatch.setattr(settings, "crossref_email", "researcher@example.org")

    adapter = get_adapter("crossref", **tasks._adapter_kwargs("crossref"))

    assert adapter._email == "researcher@example.org"


def test_get_adapter_with_settings_wires_semantic_scholar_api_key(monkeypatch):
    monkeypatch.setattr(settings, "semantic_scholar_api_key", "s2-secret")

    adapter = get_adapter("semanticscholar", **tasks._adapter_kwargs("semanticscholar"))

    assert adapter._api_key == "s2-secret"


def test_get_adapter_with_settings_wires_lens_api_key(monkeypatch):
    test_value = "lens-" + "test-token"
    monkeypatch.setattr(settings, "lens_api_key", test_value, raising=False)

    adapter = get_adapter("lens", **tasks._adapter_kwargs("lens"))

    assert adapter._api_key == test_value


def test_get_adapter_without_settings_configured_keeps_adapter_defaults(monkeypatch):
    monkeypatch.setattr(settings, "pubmed_api_key", "")
    monkeypatch.setattr(settings, "pubmed_rate_limit", 3.0)

    adapter = get_adapter("pubmed", **tasks._adapter_kwargs("pubmed"))

    assert adapter._client.api_key == ""
    assert adapter._client.rate_limit == 3.0


# ---------------------------------------------------------------------------
# (a) iCite enrichment failure must not fail an otherwise-successful search
# ---------------------------------------------------------------------------

@pytest.fixture
def task_session_factory(db):
    """A second sessionmaker bound to the SAME connection as the `db` fixture,
    so `_run_search`'s internally-created `SessionLocal()` session commits into
    the same test-scoped (auto-rolled-back) transaction and its writes are
    immediately visible to the test's own `db` session."""
    return sessionmaker(bind=db.connection())


def test_run_search_rejects_unconfigured_lens_without_creating_adapter(
    db, monkeypatch, task_session_factory
):
    query = _make_query(db)
    monkeypatch.setattr(settings, "lens_api_key", "")
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)

    def unexpected_adapter(*args, **kwargs):
        pytest.fail("adapter should not be created without a Lens API key")

    monkeypatch.setattr(tasks, "get_adapter", unexpected_adapter)

    with pytest.raises(RuntimeError, match="BIBMEDED_LENS_API_KEY"):
        asyncio.run(
            tasks._run_search(
                _StubTask(), query.id, "lens", None, None, tasks.DEFAULT_MAX_RESULTS
            )
        )

    db.expire_all()
    assert db.get(SearchQuery, query.id).status == QueryStatus.failed


def test_run_search_enrichment_failure_still_completes_with_result_count(
    db, monkeypatch, task_session_factory
):
    query = _make_query(db)
    records = [_make_record("3001"), _make_record("3002")]
    stub_adapter = _StubAdapter(ids=["3001", "3002"], records=records)

    monkeypatch.setattr(tasks, "get_adapter", lambda source, **kwargs: stub_adapter)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    monkeypatch.setattr(
        tasks, "ICiteClient", lambda: _FailingICiteClient(RuntimeError("iCite 503"))
    )

    asyncio.run(
        tasks._run_search(_StubTask(), query.id, "pubmed", None, None, tasks.DEFAULT_MAX_RESULTS)
    )

    db.expire_all()
    refreshed = db.get(SearchQuery, query.id)
    assert refreshed.status == QueryStatus.completed
    assert refreshed.result_count == 2

    pubs = db.query(Publication).filter(Publication.query_id == query.id).all()
    assert len(pubs) == 2

    enrichment_steps = (
        db.query(MethodologyStep)
        .filter(MethodologyStep.query_id == query.id, MethodologyStep.phase == "enrichment")
        .all()
    )
    assert len(enrichment_steps) == 1
    step = enrichment_steps[0]
    assert step.parameters["status"] == "failed"
    assert "iCite 503" in step.parameters["error"]
    assert step.records_in == 2

    # Regression guard for the CRITICAL bug: the enrichment failure's
    # db.rollback() must not wipe the flush-only 'fetch' (and 'search')
    # MethodologyStep rows logged earlier in the same task run.
    fetch_steps = (
        db.query(MethodologyStep)
        .filter(MethodologyStep.query_id == query.id, MethodologyStep.phase == "fetch")
        .all()
    )
    assert len(fetch_steps) == 1
    assert fetch_steps[0].records_out == 2

    search_steps = (
        db.query(MethodologyStep)
        .filter(MethodologyStep.query_id == query.id, MethodologyStep.phase == "search")
        .all()
    )
    assert len(search_steps) == 1


def test_run_search_enrichment_success_updates_citation_counts(
    db, monkeypatch, task_session_factory
):
    """Regression guard: wrapping enrichment in try/except must not break the
    normal, successful enrichment path."""
    query = _make_query(db)
    records = [_make_record("6001"), _make_record("6002")]
    stub_adapter = _StubAdapter(ids=["6001", "6002"], records=records)

    class _WorkingICiteClient:
        async def get_citations(self, pmids):
            return {"6001": 42, "6002": 7}

        async def close(self):
            pass

    monkeypatch.setattr(tasks, "get_adapter", lambda source, **kwargs: stub_adapter)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    monkeypatch.setattr(tasks, "ICiteClient", lambda: _WorkingICiteClient())

    asyncio.run(
        tasks._run_search(
            _StubTask(), query.id, "pubmed", None, None, tasks.DEFAULT_MAX_RESULTS
        )
    )

    db.expire_all()
    refreshed = db.get(SearchQuery, query.id)
    assert refreshed.status == QueryStatus.completed
    assert refreshed.result_count == 2

    pubs = {p.pmid: p for p in db.query(Publication).filter(Publication.query_id == query.id).all()}
    assert pubs["6001"].citation_count == 42
    assert pubs["6002"].citation_count == 7

    enrichment_steps = (
        db.query(MethodologyStep)
        .filter(MethodologyStep.query_id == query.id, MethodologyStep.phase == "enrichment")
        .all()
    )
    assert len(enrichment_steps) == 1
    assert enrichment_steps[0].parameters["status"] == "completed"
    assert enrichment_steps[0].parameters["enriched"] == 2


def test_run_search_enrichment_db_fatal_exception_still_propagates(
    db, monkeypatch, task_session_factory
):
    """A dropped DB connection during enrichment is a batch-level failure, not
    a best-effort-metadata failure — it must still fail the whole task."""
    query = _make_query(db)
    records = [_make_record("4001")]
    stub_adapter = _StubAdapter(ids=["4001"], records=records)

    class _BrokenICiteClient:
        async def get_citations(self, pmids):
            raise OperationalError("SELECT 1", {}, Exception("connection lost"))

        async def close(self):
            pass

    monkeypatch.setattr(tasks, "get_adapter", lambda source, **kwargs: stub_adapter)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    monkeypatch.setattr(tasks, "ICiteClient", lambda: _BrokenICiteClient())

    with pytest.raises(OperationalError):
        asyncio.run(
            tasks._run_search(
                _StubTask(), query.id, "pubmed", None, None, tasks.DEFAULT_MAX_RESULTS
            )
        )

    db.expire_all()
    refreshed = db.get(SearchQuery, query.id)
    assert refreshed.status == QueryStatus.failed


def test_run_search_no_pmids_skips_enrichment_entirely(db, monkeypatch, task_session_factory):
    """Non-PubMed sources never call iCite at all — no enrichment step should
    be logged, and the search should complete normally."""
    query = _make_query(db)
    query.database = "openalex"
    db.commit()
    records = [_make_record("W5001")]
    stub_adapter = _StubAdapter(ids=["W5001"], records=records)

    called = {"get_citations": False}

    class _AssertNotCalledICiteClient:
        async def get_citations(self, pmids):
            called["get_citations"] = True
            return {}

        async def close(self):
            pass

    monkeypatch.setattr(tasks, "get_adapter", lambda source, **kwargs: stub_adapter)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    monkeypatch.setattr(tasks, "ICiteClient", lambda: _AssertNotCalledICiteClient())

    asyncio.run(
        tasks._run_search(
            _StubTask(), query.id, "openalex", None, None, tasks.DEFAULT_MAX_RESULTS
        )
    )

    assert called["get_citations"] is False
    db.expire_all()
    refreshed = db.get(SearchQuery, query.id)
    assert refreshed.status == QueryStatus.completed
    assert refreshed.result_count == 1
    enrichment_steps = (
        db.query(MethodologyStep)
        .filter(MethodologyStep.query_id == query.id, MethodologyStep.phase == "enrichment")
        .all()
    )
    assert enrichment_steps == []


# ---------------------------------------------------------------------------
# (d) Per-project publication scoping — a PMID claimed by one project must not
#     starve a second, unrelated project that legitimately retrieves it.
# ---------------------------------------------------------------------------

def test_persist_records_same_pmid_persists_independently_per_project(db):
    """Project A persists PMID X; Project B fetching the same record must get its
    OWN Publication row, not have it silently rolled back by a global-unique clash."""
    query_a = _make_query(db, project_name="Project A")
    query_b = _make_query(db, project_name="Project B")

    record = _make_record("12345", doi="10.1/shared")

    count_a, pmids_a = tasks._persist_records(db, [record], query_a.id, query_a.project_id)
    count_b, pmids_b = tasks._persist_records(db, [record], query_b.id, query_b.project_id)

    assert count_a == 1
    assert count_b == 1  # not starved by Project A's prior claim

    pubs_a = db.query(Publication).filter(Publication.query_id == query_a.id).all()
    pubs_b = db.query(Publication).filter(Publication.query_id == query_b.id).all()
    assert [p.pmid for p in pubs_a] == ["12345"]
    assert [p.pmid for p in pubs_b] == ["12345"]
    assert pubs_a[0].project_id == query_a.project_id
    assert pubs_b[0].project_id == query_b.project_id


def test_persist_records_intra_project_dedup_uses_external_ids_pmid(db):
    """A PubMed-first paper (Publication.pmid = its PMID, no DOI) re-arriving via an
    OpenAlex record whose source_id is a W-id but whose external_ids carries the same
    PMID must be recognised as a duplicate within the same project."""
    query = _make_query(db)

    pubmed_record = _make_record("777", doi=None)  # source_id == pmid, no DOI
    openalex_record = _make_openalex_record("W777", pmid="777", doi=None)

    count_first, _ = tasks._persist_records(db, [pubmed_record], query.id, query.project_id)
    count_second, _ = tasks._persist_records(db, [openalex_record], query.id, query.project_id)

    assert count_first == 1
    assert count_second == 0  # same paper, matched via external_ids['pmid']

    pubs = db.query(Publication).filter(Publication.query_id == query.id).all()
    assert len(pubs) == 1
    assert pubs[0].pmid == "777"


# ---------------------------------------------------------------------------
# (e) SoftTimeLimitExceeded must propagate out of the per-record loop, not be
#     swallowed by the generic `except Exception` in _persist_records.
# ---------------------------------------------------------------------------

def test_persist_records_propagates_soft_time_limit_exceeded(db, monkeypatch):
    query = _make_query(db)
    records = [
        _make_record("9001", affiliation="Good Hospital, USA"),
        _make_record("9002", affiliation="TRIGGER_TIMEOUT"),
        _make_record("9003", affiliation="Another Hospital, USA"),
    ]

    real_extract_country = tasks.extract_country

    def timeout_extract_country(affiliation):
        if affiliation == "TRIGGER_TIMEOUT":
            raise SoftTimeLimitExceeded()
        return real_extract_country(affiliation)

    monkeypatch.setattr(tasks, "extract_country", timeout_extract_country)

    with pytest.raises(SoftTimeLimitExceeded):
        tasks._persist_records(db, records, query.id, query.project_id)

    # The record that triggered the soft timeout must not have been silently
    # skipped-and-continued; the batch aborts instead of finishing 9001/9003
    # and swallowing the timeout as if it were an ordinary bad record.
    pubs = db.query(Publication).filter(Publication.pmid == "9002").first()
    assert pubs is None


# ---------------------------------------------------------------------------
# (f) Journal lookups must be prefetched per-batch, not re-queried per record
#     (N+1 regression guard, mirroring authors/affiliations/keywords).
# ---------------------------------------------------------------------------

def test_persist_records_prefetches_journals_avoiding_n_plus_one(db):
    query = _make_query(db)
    # All records share the same journal_name ("Journal of Testing" from
    # _make_record) so a non-prefetched implementation would issue one
    # SELECT per record for the *same* journal row.
    records = [_make_record(f"70{i:02d}") for i in range(5)]

    select_statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if "journals" in statement.lower() and statement.strip().lower().startswith("select"):
            select_statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    try:
        count, pmids = tasks._persist_records(db, records, query.id, query.project_id)
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor_execute)

    assert count == 5
    assert len(select_statements) <= 1, (
        f"expected at most 1 SELECT against journals (batch prefetch), "
        f"got {len(select_statements)}: {select_statements}"
    )


def test_persist_records_evicts_phantom_journal_on_savepoint_rollback(db, monkeypatch):
    """A new Journal created+rolled-back within a failed record's savepoint must not
    leave a phantom entry in the prefetch cache for a later record in the same batch."""
    query = _make_query(db)
    records = [
        _make_record("9101", affiliation="TRIGGER_FAIL", title="First (fails)"),
        _make_record("9102", affiliation="Good Hospital, USA", title="Second (succeeds)"),
    ]

    real_extract_country = tasks.extract_country

    def flaky_extract_country(affiliation):
        if affiliation == "TRIGGER_FAIL":
            raise ValueError("simulated per-record failure after journal creation")
        return real_extract_country(affiliation)

    monkeypatch.setattr(tasks, "extract_country", flaky_extract_country)

    count, pmids = tasks._persist_records(db, records, query.id, query.project_id)

    assert count == 1
    assert pmids == ["9102"]
    pub = db.query(Publication).filter(Publication.pmid == "9102").first()
    assert pub is not None
    assert pub.journal_id is not None
    assert pub.journal.name_normalized == "journal of testing"


# ---------------------------------------------------------------------------
# (g) request_id correlation — API → Celery task log records & methodology log
# ---------------------------------------------------------------------------

def test_run_search_binds_request_id_into_log_records_and_methodology_steps(
    db, monkeypatch, task_session_factory, caplog
):
    query = _make_query(db)
    records = [_make_record("8001")]
    stub_adapter = _StubAdapter(ids=["8001"], records=records)

    monkeypatch.setattr(tasks, "get_adapter", lambda source, **kwargs: stub_adapter)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    monkeypatch.setattr(
        tasks, "ICiteClient", lambda: _FailingICiteClient(RuntimeError("iCite down"))
    )

    with caplog.at_level(logging.INFO, logger="app.workers.tasks"):
        asyncio.run(
            tasks._run_search(
                _StubTask(), query.id, "pubmed", None, None, tasks.DEFAULT_MAX_RESULTS,
                request_id="req-abc123",
            )
        )

    assert any(getattr(r, "request_id", None) == "req-abc123" for r in caplog.records), (
        "expected at least one log record emitted during _run_search to carry "
        "request_id='req-abc123'"
    )

    db.expire_all()
    steps = db.query(MethodologyStep).filter(MethodologyStep.query_id == query.id).all()
    assert steps
    assert all(s.parameters.get("request_id") == "req-abc123" for s in steps)


def test_run_search_defaults_request_id_when_not_provided(db, monkeypatch, task_session_factory):
    """Backwards compatibility: callers (e.g. the legacy run_pubmed_search task) that
    don't pass request_id must not crash — methodology steps just carry a sentinel."""
    query = _make_query(db)
    records = [_make_record("8101")]
    stub_adapter = _StubAdapter(ids=["8101"], records=records)

    class _WorkingICiteClient:
        async def get_citations(self, pmids):
            return {}

        async def close(self):
            pass

    monkeypatch.setattr(tasks, "get_adapter", lambda source, **kwargs: stub_adapter)
    monkeypatch.setattr(tasks, "SessionLocal", task_session_factory)
    monkeypatch.setattr(tasks, "ICiteClient", lambda: _WorkingICiteClient())

    asyncio.run(
        tasks._run_search(_StubTask(), query.id, "pubmed", None, None, tasks.DEFAULT_MAX_RESULTS)
    )

    db.expire_all()
    refreshed = db.get(SearchQuery, query.id)
    assert refreshed.status == QueryStatus.completed
