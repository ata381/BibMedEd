import asyncio
import logging
from datetime import datetime, timezone

from celery.exceptions import SoftTimeLimitExceeded

logger = logging.getLogger(__name__)

from app.adapters.base import RawRecord
from app.adapters.registry import get_adapter
from app.database import SessionLocal
from app.models import (
    Affiliation, Author, Journal, Keyword, KeywordType,
    Publication, SearchQuery, QueryStatus,
)
from app.models.methodology import MethodologyStep
from app.services.cleaning import (
    _normalize_doi,
    deduplicate_cross_source,
    extract_country,
    normalize_name,
)
from app.services.icite import ICiteClient
from app.workers.celery_app import celery_app


def _norm_cache(cache: dict[str, str], value: str) -> str:
    """Memoize normalize_name() within a batch so each unique string is normalized once."""
    if value not in cache:
        cache[value] = normalize_name(value)
    return cache[value]


def _prefetch_lookup_caches(db, records: list[RawRecord]) -> tuple[
    dict[str, str], dict[str, Author], dict[str, Affiliation], dict[tuple[str, KeywordType], Keyword]
]:
    """Build single-query lookup dicts for authors, affiliations, and keywords used by this batch.

    Collapses ~14k per-record SELECTs (2k records * 5 authors * 2 lookups + keywords) into a
    handful of `WHERE column IN (...)` queries.
    """
    norm: dict[str, str] = {}
    author_names: set[str] = set()
    affil_names: set[str] = set()
    mesh_terms: set[str] = set()
    kw_terms: set[str] = set()
    for r in records:
        for a in r.authors:
            author_names.add(_norm_cache(norm, a.name))
            if a.affiliation:
                affil_names.add(_norm_cache(norm, a.affiliation))
        for t in r.mesh_terms:
            mesh_terms.add(_norm_cache(norm, t))
        for t in r.keywords:
            kw_terms.add(_norm_cache(norm, t))

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
    return norm, authors_by_norm, affils_by_norm, keywords_by_key


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


def _persist_records(db, records: list[RawRecord], query_id: int) -> tuple[int, list[str]]:
    """Persist a batch of RawRecords. Returns (count_persisted, persisted_pmids).

    Each record is wrapped in a SAVEPOINT so a single bad row does not roll back its
    siblings. Authors, affiliations, and keywords are bulk-prefetched per batch to avoid
    N+1 SELECTs. Cache entries added during a record that ultimately rolls back are
    evicted so subsequent records do not reuse phantom ORM objects whose underlying rows
    no longer exist.
    """
    norm, authors_by_norm, affils_by_norm, keywords_by_key = _prefetch_lookup_caches(db, records)

    persisted = 0
    persisted_pmids: list[str] = []
    pub_authors_tbl = Publication.__table__.metadata.tables["publication_authors"]
    for record in records:
        sp = db.begin_nested()
        # Track keys we add to caches in this record so we can evict on rollback.
        added_author_keys: list[str] = []
        added_affil_keys: list[str] = []
        added_keyword_keys: list[tuple[str, KeywordType]] = []
        try:
            journal = None
            if record.journal_name:
                journal = db.query(Journal).filter(Journal.name == record.journal_name).first()
                if not journal:
                    journal = Journal(
                        name=record.journal_name,
                        issn=record.journal_issn,
                        name_normalized=_norm_cache(norm, record.journal_name),
                    )
                    db.add(journal)
                    db.flush()

            normalized_doi = _normalize_doi(record.external_ids.get("doi") or record.doi)
            existing_q = db.query(Publication).filter(Publication.pmid == record.source_id)
            if normalized_doi:
                existing_q = db.query(Publication).filter(
                    (Publication.pmid == record.source_id) | (Publication.doi == normalized_doi)
                )
            existing = existing_q.first()
            if existing:
                sp.rollback()
                continue

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
            )
            db.add(pub)
            db.flush()

            for pos, author_data in enumerate(record.authors):
                a_norm = _norm_cache(norm, author_data.name)
                author = authors_by_norm.get(a_norm)
                if author is None:
                    author = Author(name=author_data.name, orcid=author_data.orcid, name_normalized=a_norm)
                    db.add(author)
                    db.flush()
                    authors_by_norm[a_norm] = author
                    added_author_keys.append(a_norm)
                db.execute(
                    pub_authors_tbl.insert().values(
                        publication_id=pub.id, author_id=author.id, author_position=pos
                    )
                )

                if author_data.affiliation:
                    af_norm = _norm_cache(norm, author_data.affiliation)
                    aff = affils_by_norm.get(af_norm)
                    if aff is None:
                        aff = Affiliation(
                            name=author_data.affiliation,
                            country=extract_country(author_data.affiliation),
                            name_normalized=af_norm,
                        )
                        db.add(aff)
                        db.flush()
                        affils_by_norm[af_norm] = aff
                        added_affil_keys.append(af_norm)
                    if aff not in author.affiliations:
                        author.affiliations.append(aff)

            for term in record.mesh_terms:
                k_norm = _norm_cache(norm, term)
                key = (k_norm, KeywordType.mesh_term)
                pre_existed = key in keywords_by_key
                kw = _get_or_create_keyword(db, keywords_by_key, term, k_norm, KeywordType.mesh_term)
                if not pre_existed:
                    added_keyword_keys.append(key)
                pub.keywords.append(kw)

            for term in record.keywords:
                k_norm = _norm_cache(norm, term)
                key = (k_norm, KeywordType.author_keyword)
                pre_existed = key in keywords_by_key
                kw = _get_or_create_keyword(db, keywords_by_key, term, k_norm, KeywordType.author_keyword)
                if not pre_existed:
                    added_keyword_keys.append(key)
                pub.keywords.append(kw)

            sp.commit()
            persisted += 1
            persisted_pmids.append(pub.pmid)
        except Exception as exc:
            logger.warning("Skipping record %s: %s", record.source_id, exc)
            sp.rollback()
            # Evict phantom cache entries — their underlying rows were rolled back.
            for k in added_author_keys:
                authors_by_norm.pop(k, None)
            for k in added_affil_keys:
                affils_by_norm.pop(k, None)
            for k in added_keyword_keys:
                keywords_by_key.pop(k, None)
            continue

    db.commit()
    return persisted, persisted_pmids


def _log_step(db, query_id: int, step_order: int, phase: str, source: str,
              action: str, records_in: int, records_out: int, parameters: dict | None = None) -> None:
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


@celery_app.task(bind=True, name="app.workers.tasks.run_search", soft_time_limit=600, time_limit=660)
def run_search(self, query_id: int, source: str = "pubmed", year_start: str | None = None,
               year_end: str | None = None, max_results: int = DEFAULT_MAX_RESULTS):
    asyncio.run(_run_search(self, query_id, source, year_start, year_end, max_results))


# Register the old task name so queued messages from before the rename still get processed
@celery_app.task(bind=True, name="app.workers.tasks.run_pubmed_search", soft_time_limit=600, time_limit=660)
def run_pubmed_search(self, query_id: int):
    asyncio.run(_run_search(self, query_id, "pubmed", None, None, DEFAULT_MAX_RESULTS))


async def _run_search(task, query_id: int, source: str, year_start: str | None = None,
                      year_end: str | None = None, max_results: int = DEFAULT_MAX_RESULTS):
    adapter = get_adapter(source)
    db = SessionLocal()
    icite = ICiteClient()
    try:
        query = db.get(SearchQuery, query_id)
        if not query:
            return
        query.status = QueryStatus.running
        db.commit()

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
        if query.created_at:
            # SQLite returns naive datetimes; Postgres returns tz-aware. astimezone handles
            # both: naive datetimes are first localized to UTC, aware ones are converted.
            ca = query.created_at
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            searched_at_iso = ca.astimezone(timezone.utc).isoformat()
        else:
            searched_at_iso = None
        _log_step(db, query_id, step_order=1, phase="search", source=source,
                  action=f"{adapter.methodology_label()} search",
                  records_in=0, records_out=total_found,
                  parameters={"query": query.query_string, "database": source,
                              "max_results": max_results, "capped": total_found > max_results,
                              "searched_at": searched_at_iso})

        # Phase 2: Fetch + cross-source dedup + persist in chunks
        persisted = 0
        all_persisted_pmids: list[str] = []
        track_pmids = source == "pubmed"  # only PubMed source needs iCite enrichment
        cross_source_removed = 0
        dedup_breakdown: dict[str, int] = {"doi": 0, "pmid": 0}
        async for records in adapter.fetch_stream(all_ids, batch_size=FETCH_BATCH_SIZE):
            deduped, batch_removed, batch_breakdown = deduplicate_cross_source(records)
            cross_source_removed += batch_removed
            for k, v in batch_breakdown.items():
                dedup_breakdown[k] = dedup_breakdown.get(k, 0) + v
            count, batch_pmids = _persist_records(db, deduped, query_id)
            persisted += count
            if track_pmids:
                all_persisted_pmids.extend(batch_pmids)
            task.update_state(
                state="PROGRESS",
                meta={"phase": "fetch", "current": persisted, "total": len(all_ids)},
            )

        _log_step(db, query_id, step_order=2, phase="fetch", source=source,
                  action=f"Batch fetch via {adapter.methodology_label()}",
                  records_in=len(all_ids), records_out=persisted,
                  parameters={"batch_size": FETCH_BATCH_SIZE})

        if cross_source_removed:
            _log_step(db, query_id, step_order=3, phase="dedup", source=source,
                      action="Cross-source deduplication on DOI and PMID",
                      records_in=persisted + cross_source_removed, records_out=persisted,
                      parameters={"method": "exact-match", "fields": "doi,pmid",
                                  "removed_by": dedup_breakdown})

        # Phase 4: iCite enrichment (PubMed-sourced records only)
        if track_pmids and all_persisted_pmids:
            citation_counts = await icite.get_citations(all_persisted_pmids)
            if citation_counts:
                pubs_to_update = (
                    db.query(Publication)
                    .filter(Publication.pmid.in_(citation_counts.keys()))
                    .all()
                )
                for pub in pubs_to_update:
                    pub.citation_count = citation_counts.get(pub.pmid)
            db.commit()
            enriched_count = len(citation_counts)
            _log_step(db, query_id, step_order=4, phase="enrichment", source="icite",
                      action="iCite citation count enrichment",
                      records_in=persisted, records_out=persisted,
                      parameters={"source": "NIH iCite", "enriched": enriched_count,
                                  "missing": persisted - enriched_count})

        query.status = QueryStatus.completed
        query.result_count = persisted
        ids_submitted_for_fetch = len(all_ids)
        query.duplicate_count = max(0, ids_submitted_for_fetch - persisted)
        query.executed_at = datetime.now(timezone.utc)
        db.commit()
    except SoftTimeLimitExceeded:
        query = db.get(SearchQuery, query_id)
        if query:
            query.status = QueryStatus.failed
            db.commit()
        raise
    except Exception as e:
        query = db.get(SearchQuery, query_id)
        if query:
            query.status = QueryStatus.failed
            db.commit()
        raise e
    finally:
        await adapter.close()
        await icite.close()
        db.close()
