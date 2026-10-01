import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import NamedTuple

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.exc import DisconnectionError, OperationalError

logger = logging.getLogger(__name__)

# DB-level exceptions that should propagate immediately rather than be swallowed
# per-record. A dropped connection isn't a bad record — it's a batch-level failure.
_FATAL_DB_EXCEPTIONS = (OperationalError, DisconnectionError)

from bibmeded.adapters.base import RawRecord
from bibmeded.adapters.registry import get_adapter
from bibmeded.adapters.settings import adapter_configuration_error, adapter_kwargs as _adapter_kwargs
from bibmeded.database import SessionLocal
from bibmeded.models import (
    Affiliation, Author, Journal, Keyword, KeywordType,
    Publication, SearchQuery, QueryStatus,
)
from bibmeded.models.methodology import MethodologyStep
from bibmeded.services.cleaning import (
    _normalize_doi,
    deduplicate_cross_source,
    extract_country,
    normalize_name,
)
from bibmeded.services.icite import ICiteClient
from bibmeded.workers.celery_app import celery_app


def _norm_cache(cache: dict[str, str], value: str) -> str:
    """Memoize normalize_name() within a batch so each unique string is normalized once."""
    if value not in cache:
        cache[value] = normalize_name(value)
    return cache[value]


def _prefetch_lookup_caches(db, records: list[RawRecord]) -> tuple[
    dict[str, str], dict[str, Author], dict[str, Affiliation],
    dict[tuple[str, KeywordType], Keyword], dict[str, Journal],
]:
    """Build single-query lookup dicts for authors, affiliations, keywords, and journals
    used by this batch.

    Collapses ~14k per-record SELECTs (2k records * 5 authors * 2 lookups + keywords +
    journal) into a handful of `WHERE column IN (...)` queries.
    """
    norm: dict[str, str] = {}
    author_names: set[str] = set()
    affil_names: set[str] = set()
    mesh_terms: set[str] = set()
    kw_terms: set[str] = set()
    journal_names: set[str] = set()
    for r in records:
        for a in r.authors:
            author_names.add(_norm_cache(norm, a.name))
            if a.affiliation:
                affil_names.add(_norm_cache(norm, a.affiliation))
        for t in r.mesh_terms:
            mesh_terms.add(_norm_cache(norm, t))
        for t in r.keywords:
            kw_terms.add(_norm_cache(norm, t))
        if r.journal_name:
            journal_names.add(_norm_cache(norm, r.journal_name))

    authors_by_norm: dict[str, Author] = {}
    if author_names:
        for a in db.query(Author).filter(Author.name_normalized.in_(author_names)).all():
            authors_by_norm[a.name_normalized] = a
    affils_by_norm: dict[str, Affiliation] = {}
    if affil_names:
        for a in db.query(Affiliation).filter(Affiliation.name_normalized.in_(affil_names)).all():
            affils_by_norm[a.name_normalized] = a
    keywords_by_key: dict[tuple[str, KeywordType], Keyword] = {}
    if mesh_terms:
        for k in db.query(Keyword).filter(
            Keyword.term_normalized.in_(mesh_terms),
            Keyword.type == KeywordType.mesh_term,
        ).all():
            keywords_by_key[(k.term_normalized, KeywordType.mesh_term)] = k
    if kw_terms:
        for k in db.query(Keyword).filter(
            Keyword.term_normalized.in_(kw_terms),
            Keyword.type == KeywordType.author_keyword,
        ).all():
            keywords_by_key[(k.term_normalized, KeywordType.author_keyword)] = k
    journals_by_norm: dict[str, Journal] = {}
    if journal_names:
        for j in db.query(Journal).filter(Journal.name_normalized.in_(journal_names)).all():
            journals_by_norm[j.name_normalized] = j
    return norm, authors_by_norm, affils_by_norm, keywords_by_key, journals_by_norm


def _get_or_create_keyword(
    db, cache: dict[tuple[str, KeywordType], Keyword], term: str, normalized: str, type_: KeywordType,
) -> Keyword:
    key = (normalized, type_)
    kw = cache.get(key)
    if kw is None:
        kw = Keyword(term=term, type=type_, term_normalized=normalized)
        db.add(kw)
        db.flush()
        cache[key] = kw
    return kw


MAX_FAILURE_ERROR_CHARS = 300
# Bounds the per-record detail stored on the fetch methodology step; the step's
# `persist_failed` count always carries the true total.
MAX_LOGGED_PERSIST_FAILURES = 100


class PersistResult(NamedTuple):
    persisted: int
    persisted_pmids: list[str]
    # One {"source_id", "source_database", "error"} dict per record whose savepoint
    # was rolled back, so callers can write it into the methodology log.
    failures: list[dict[str, str]]


class _BatchCaches(NamedTuple):
    norm: dict[str, str]
    authors: dict[str, Author]
    affiliations: dict[str, Affiliation]
    keywords: dict[tuple[str, KeywordType], Keyword]
    journals: dict[str, Journal]


@dataclass
class _SavepointCacheAdditions:
    """Cache keys added inside one record's savepoint, evicted if it rolls back."""

    authors: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    keywords: list[tuple[str, KeywordType]] = field(default_factory=list)
    journal: str | None = None

    def evict_from(self, caches: _BatchCaches) -> None:
        for k in self.authors:
            caches.authors.pop(k, None)
        for k in self.affiliations:
            caches.affiliations.pop(k, None)
        for k in self.keywords:
            caches.keywords.pop(k, None)
        if self.journal is not None:
            caches.journals.pop(self.journal, None)


def _describe_failure(record: RawRecord, exc: Exception) -> dict[str, str]:
    # DB driver messages embed the full statement and bound parameters; truncate so
    # one bad row cannot bloat the methodology log.
    return {
        "source_id": record.source_id,
        "source_database": record.source_database,
        "error": f"{type(exc).__name__}: {exc}"[:MAX_FAILURE_ERROR_CHARS],
    }


def _find_existing_publication(
    db, record: RawRecord, normalized_doi: str | None, project_id: int,
) -> Publication | None:
    # `Publication.pmid` stores source_id (the source-native primary id), but a
    # non-PubMed record's real PMID lives in external_ids["pmid"]. Check both so
    # a PubMed-first-persisted paper (Publication.pmid == its PMID, often no DOI)
    # is deduped when the same paper re-arrives via OpenAlex/CrossRef.
    pmid_candidates = {record.source_id}
    real_pmid = record.external_ids.get("pmid")
    if real_pmid:
        pmid_candidates.add(real_pmid)
    id_match = Publication.pmid.in_(pmid_candidates)
    if normalized_doi:
        id_match = id_match | (Publication.doi == normalized_doi)
    return (
        db.query(Publication)
        .filter(Publication.project_id == project_id, id_match)
        .first()
    )


def _get_or_create_journal(
    db, record: RawRecord, caches: _BatchCaches, additions: _SavepointCacheAdditions,
) -> Journal | None:
    if not record.journal_name:
        return None
    # Case-insensitive lookup via name_normalized so "JAMA"/"Jama" don't produce
    # duplicate Journal rows. Prefetched per-batch (see _prefetch_lookup_caches) to
    # avoid an N+1 SELECT per record.
    j_norm = _norm_cache(caches.norm, record.journal_name)
    journal = caches.journals.get(j_norm)
    if journal is None:
        journal = Journal(name=record.journal_name, issn=record.journal_issn, name_normalized=j_norm)
        db.add(journal)
        db.flush()
        caches.journals[j_norm] = journal
        additions.journal = j_norm
    return journal


def _attach_authors(
    db, pub: Publication, record: RawRecord, caches: _BatchCaches,
    additions: _SavepointCacheAdditions, pub_authors_tbl,
) -> None:
    for pos, author_data in enumerate(record.authors):
        a_norm = _norm_cache(caches.norm, author_data.name)
        author = caches.authors.get(a_norm)
        if author is None:
            author = Author(name=author_data.name, orcid=author_data.orcid, name_normalized=a_norm)
            db.add(author)
            db.flush()
            caches.authors[a_norm] = author
            additions.authors.append(a_norm)
        db.execute(
            pub_authors_tbl.insert().values(
                publication_id=pub.id, author_id=author.id, author_position=pos
            )
        )

        if author_data.affiliation:
            af_norm = _norm_cache(caches.norm, author_data.affiliation)
            aff = caches.affiliations.get(af_norm)
            if aff is None:
                aff = Affiliation(
                    name=author_data.affiliation,
                    country=extract_country(author_data.affiliation),
                    name_normalized=af_norm,
                )
                db.add(aff)
                db.flush()
                caches.affiliations[af_norm] = aff
                additions.affiliations.append(af_norm)
            if aff not in author.affiliations:
                author.affiliations.append(aff)


def _attach_keywords(
    db, pub: Publication, record: RawRecord, caches: _BatchCaches,
    additions: _SavepointCacheAdditions,
) -> None:
    for terms, type_ in (
        (record.mesh_terms, KeywordType.mesh_term),
        (record.keywords, KeywordType.author_keyword),
    ):
        for term in terms:
            k_norm = _norm_cache(caches.norm, term)
            key = (k_norm, type_)
            pre_existed = key in caches.keywords
            kw = _get_or_create_keyword(db, caches.keywords, term, k_norm, type_)
            if not pre_existed:
                additions.keywords.append(key)
            pub.keywords.append(kw)


def _persist_one(
    db, record: RawRecord, query_id: int, project_id: int, caches: _BatchCaches,
    additions: _SavepointCacheAdditions, pub_authors_tbl,
) -> Publication | None:
    """Write one record inside the caller's savepoint. Returns None if the project
    already holds this paper; the existence check runs before any INSERT so that an
    empty savepoint, not an orphan Journal row, is what gets released."""
    normalized_doi = _normalize_doi(record.external_ids.get("doi") or record.doi)
    if _find_existing_publication(db, record, normalized_doi, project_id) is not None:
        return None

    journal = _get_or_create_journal(db, record, caches, additions)
    pub = Publication(
        pmid=record.source_id,
        doi=normalized_doi,
        title=record.title,
        abstract=record.abstract,
        year=record.year,
        source_database=record.source_database,
        citation_count=None,
        journal_id=journal.id if journal else None,
        query_id=query_id,
        project_id=project_id,
        external_references=list(record.references) if record.references else None,
    )
    db.add(pub)
    db.flush()
    _attach_authors(db, pub, record, caches, additions, pub_authors_tbl)
    _attach_keywords(db, pub, record, caches, additions)
    return pub


def _persist_records(
    db,
    records: list[RawRecord],
    query_id: int,
    project_id: int,
    *,
    commit: bool = True,
) -> PersistResult:
    """Persist a batch of RawRecords.

    Each record is wrapped in a SAVEPOINT so a single bad row does not roll back its
    siblings; the failed record is reported in ``PersistResult.failures`` rather than
    dropped silently. Authors, affiliations, keywords, and journals are bulk-prefetched
    per batch to avoid N+1 SELECTs. Cache entries added during a record that ultimately
    rolls back are evicted so subsequent records do not reuse phantom ORM objects whose
    underlying rows no longer exist. Set ``commit=False`` when a caller needs to add
    related rows and commit the complete operation atomically; the persisted records
    are flushed instead.

    The pre-existence check is scoped to ``project_id``: each project owns its own copy
    of a shared paper, so a PMID/DOI claimed by another project must not starve this one.
    """
    caches = _BatchCaches(*_prefetch_lookup_caches(db, records))
    pub_authors_tbl = Publication.__table__.metadata.tables["publication_authors"]

    persisted_pmids: list[str] = []
    failures: list[dict[str, str]] = []
    for record in records:
        additions = _SavepointCacheAdditions()
        try:
            # The context manager is the only thing that ends this savepoint: it
            # releases it on success and rolls it back exactly once on any exception
            # (including the re-raised ones below), so it never outlives the record.
            with db.begin_nested():
                pub = _persist_one(
                    db, record, query_id, project_id, caches, additions, pub_authors_tbl
                )
        except SoftTimeLimitExceeded:
            # Celery's cooperative soft-timeout signal is a plain Exception
            # subclass (billiard/celery.exceptions) — it must propagate so the
            # task can shut down gracefully instead of being treated as an
            # ordinary bad record and swallowed.
            raise
        except _FATAL_DB_EXCEPTIONS:
            # Connection drop / DB unavailability is a batch-level failure — don't
            # swallow it per-record and silently undercount the methodology log.
            raise
        except Exception as exc:
            logger.warning("Skipping record %s: %s", record.source_id, exc)
            # Rows created in the savepoint are gone and SQLAlchemy has already
            # expunged their ORM objects; the batch caches still point at them.
            additions.evict_from(caches)
            failures.append(_describe_failure(record, exc))
            continue
        if pub is not None:
            persisted_pmids.append(pub.pmid)

    if commit:
        db.commit()
    else:
        db.flush()
    return PersistResult(len(persisted_pmids), persisted_pmids, failures)


def _next_step_order(db, query_id: int) -> int:
    """Return MAX(step_order) + 1 for this query so re-runs and resumed tasks
    don't collide with existing methodology steps."""
    from sqlalchemy import func as sa_func
    current = db.query(sa_func.max(MethodologyStep.step_order)).filter(
        MethodologyStep.query_id == query_id
    ).scalar()
    return (current or 0) + 1


def _log_step(db, query_id: int, step_order: int | None, phase: str, source: str,
              action: str, records_in: int, records_out: int, parameters: dict | None = None) -> None:
    if step_order is None:
        step_order = _next_step_order(db, query_id)
    step = MethodologyStep(
        query_id=query_id,
        step_order=step_order,
        phase=phase,
        source=source,
        action=action,
        records_in=records_in,
        records_out=records_out,
        records_affected=abs(records_in - records_out),
        parameters=parameters or {},
        timestamp=datetime.now(timezone.utc),
    )
    db.add(step)
    db.flush()


DEFAULT_MAX_RESULTS = 2000
FETCH_BATCH_SIZE = 200

@celery_app.task(bind=True, name="bibmeded.workers.tasks.run_search", soft_time_limit=600, time_limit=660)
def run_search(self, query_id: int, source: str = "pubmed", year_start: str | None = None,
               year_end: str | None = None, max_results: int = DEFAULT_MAX_RESULTS,
               request_id: str | None = None):
    asyncio.run(_run_search(self, query_id, source, year_start, year_end, max_results, request_id))


# Register the old task name so queued messages from before the rename still get processed
@celery_app.task(bind=True, name="bibmeded.workers.tasks.run_pubmed_search", soft_time_limit=600, time_limit=660)
def run_pubmed_search(self, query_id: int):
    asyncio.run(_run_search(self, query_id, "pubmed", None, None, DEFAULT_MAX_RESULTS))


async def _run_search(task, query_id: int, source: str, year_start: str | None = None,
                      year_end: str | None = None, max_results: int = DEFAULT_MAX_RESULTS,
                      request_id: str | None = None):
    # Binds request_id onto every log record emitted by this task run so the
    # originating API request can be grepped across the API -> Celery -> DB path.
    log = logging.LoggerAdapter(logger, {"request_id": request_id or "-"})
    adapter = None
    db = SessionLocal()
    icite = ICiteClient()
    try:
        query = db.get(SearchQuery, query_id)
        if not query:
            log.warning("run_search called with unknown query_id=%s", query_id)
            return
        configuration_error = adapter_configuration_error(source)
        if configuration_error:
            raise RuntimeError(configuration_error)
        adapter = get_adapter(source, **_adapter_kwargs(source))
        query.status = QueryStatus.running
        db.commit()
        log.info("run_search started query_id=%d source=%s max_results=%d", query_id, source, max_results)

        # Phase 1: Collect IDs via streaming pagination
        all_ids: list[str] = []
        async for id_batch in adapter.search_paginated(query.query_string, year_start=year_start, year_end=year_end):
            all_ids.extend(id_batch)
            if len(all_ids) >= max_results:
                break
            task.update_state(
                state="PROGRESS",
                meta={"phase": "search", "ids_found": len(all_ids)},
            )

        total_found = len(all_ids)
        all_ids = all_ids[:max_results]  # cap to max_results
        query.raw_result_count = total_found
        db.flush()
        log.info(
            "run_search query_id=%d phase=search complete: %d ids found (capped=%s)",
            query_id, total_found, total_found > max_results,
        )
        if query.created_at:
            # SQLite returns naive datetimes; Postgres returns tz-aware. astimezone handles
            # both: naive datetimes are first localized to UTC, aware ones are converted.
            ca = query.created_at
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            searched_at_iso = ca.astimezone(timezone.utc).isoformat()
        else:
            searched_at_iso = None
        _log_step(db, query_id, step_order=None, phase="search", source=source,
                  action=f"{adapter.methodology_label()} search",
                  records_in=0, records_out=total_found,
                  parameters={"query": query.query_string, "database": source,
                              "max_results": max_results, "capped": total_found > max_results,
                              "searched_at": searched_at_iso, "request_id": request_id})

        # Phase 2: Fetch + cross-source dedup + persist in chunks
        persisted = 0
        all_persisted_pmids: list[str] = []
        track_pmids = source == "pubmed"  # only PubMed source needs iCite enrichment
        cross_source_removed = 0
        dedup_breakdown: dict[str, int] = {"doi": 0, "pmid": 0}
        persist_failures: list[dict[str, str]] = []
        async for records in adapter.fetch_stream(all_ids, batch_size=FETCH_BATCH_SIZE):
            deduped, batch_removed, batch_breakdown = deduplicate_cross_source(records)
            cross_source_removed += batch_removed
            for k, v in batch_breakdown.items():
                dedup_breakdown[k] = dedup_breakdown.get(k, 0) + v
            batch = _persist_records(db, deduped, query_id, query.project_id)
            persisted += batch.persisted
            persist_failures.extend(batch.failures)
            if track_pmids:
                all_persisted_pmids.extend(batch.persisted_pmids)
            task.update_state(
                state="PROGRESS",
                meta={"phase": "fetch", "current": persisted, "total": len(all_ids)},
            )

        _log_step(db, query_id, step_order=None, phase="fetch", source=source,
                  action=f"Batch fetch via {adapter.methodology_label()}",
                  records_in=len(all_ids), records_out=persisted,
                  parameters={"batch_size": FETCH_BATCH_SIZE, "request_id": request_id,
                              "persist_failed": len(persist_failures),
                              "persist_failures": persist_failures[:MAX_LOGGED_PERSIST_FAILURES]})

        if cross_source_removed:
            _log_step(db, query_id, step_order=None, phase="dedup", source=source,
                      action="Cross-source deduplication on DOI and PMID",
                      records_in=persisted + cross_source_removed, records_out=persisted,
                      parameters={"method": "exact-match", "fields": "doi,pmid",
                                  "removed_by": dedup_breakdown, "request_id": request_id})

        # Commit the fetch/dedup methodology steps now, before enrichment runs.
        # Enrichment failure below does db.rollback() on its own transaction —
        # if these steps were still only flush()'d (uncommitted), that rollback
        # would silently wipe them too. Committing here scopes any later
        # enrichment failure to the enrichment step alone.
        db.commit()

        # Phase 4: iCite enrichment (PubMed-sourced records only). Enrichment is
        # best-effort supplementary metadata, not a precondition for search
        # success — a transient NIH iCite outage must not fail an otherwise
        # fully-persisted search, so it gets its own try/except and a degraded
        # methodology step rather than propagating to the outer handler.
        if track_pmids and all_persisted_pmids:
            try:
                citation_counts = await icite.get_citations(all_persisted_pmids)
                if citation_counts:
                    # Scope to this project — pmid is only unique per project now, so an
                    # unscoped IN(...) would clobber other projects' rows sharing a PMID.
                    pubs_to_update = (
                        db.query(Publication)
                        .filter(
                            Publication.project_id == query.project_id,
                            Publication.pmid.in_(citation_counts.keys()),
                        )
                        .all()
                    )
                    for pub in pubs_to_update:
                        pub.citation_count = citation_counts.get(pub.pmid)
                db.commit()
                enriched_count = len(citation_counts)
                _log_step(db, query_id, step_order=None, phase="enrichment", source="icite",
                          action="iCite citation count enrichment",
                          records_in=persisted, records_out=persisted,
                          parameters={"source": "NIH iCite", "status": "completed",
                                      "enriched": enriched_count,
                                      "missing": persisted - enriched_count,
                                      "request_id": request_id})
            except SoftTimeLimitExceeded:
                raise
            except _FATAL_DB_EXCEPTIONS:
                raise
            except Exception as exc:
                db.rollback()
                log.warning("iCite enrichment failed query_id=%d: %s", query_id, exc)
                _log_step(db, query_id, step_order=None, phase="enrichment", source="icite",
                          action="iCite citation count enrichment (failed)",
                          records_in=persisted, records_out=0,
                          parameters={"source": "NIH iCite", "status": "failed",
                                      "error": str(exc), "request_id": request_id})

        query.status = QueryStatus.completed
        query.result_count = persisted
        # duplicate_count now reflects ONLY cross-source dedup, not records skipped due
        # to per-record exceptions or pre-existing DB rows (those are visible in the
        # methodology log as `records_in - records_out` of the fetch step).
        query.duplicate_count = cross_source_removed
        query.executed_at = datetime.now(timezone.utc)
        db.commit()
        log.info(
            "run_search query_id=%d completed: persisted=%d cross_source_removed=%d",
            query_id, persisted, cross_source_removed,
        )
    except SoftTimeLimitExceeded:
        query = db.get(SearchQuery, query_id)
        if query:
            query.status = QueryStatus.failed
            db.commit()
        raise
    except Exception:
        # log.exception captures the full traceback into structured log aggregators
        # (Sentry, CloudWatch) keyed to the query_id, even though the bare `raise` below
        # already preserves the traceback for Celery's own handler.
        log.exception("run_search failed query_id=%s", query_id)
        query = db.get(SearchQuery, query_id)
        if query:
            query.status = QueryStatus.failed
            db.commit()
        raise
    finally:
        if adapter is not None:
            await adapter.close()
        await icite.close()
        db.close()
