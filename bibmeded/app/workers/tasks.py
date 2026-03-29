import asyncio
from datetime import datetime, timezone

from celery.exceptions import SoftTimeLimitExceeded

from app.adapters.base import RawRecord
from app.adapters.registry import get_adapter
from app.database import SessionLocal
from app.models import (
    Affiliation, Author, Journal, Keyword, KeywordType,
    Publication, SearchQuery, QueryStatus,
)
from app.models.methodology import MethodologyStep
from app.services.cleaning import extract_country, normalize_name
from app.services.icite import ICiteClient
from app.workers.celery_app import celery_app


def _persist_records(db, records: list[RawRecord], query_id: int) -> int:
    """Persist a batch of RawRecords to the database. Returns count persisted."""
    persisted = 0
    for record in records:
        journal = None
        if record.journal_name:
            journal = db.query(Journal).filter(Journal.name == record.journal_name).first()
            if not journal:
                journal = Journal(
                    name=record.journal_name,
                    issn=record.journal_issn,
                    name_normalized=normalize_name(record.journal_name),
                )
                db.add(journal)
                db.flush()

        existing = db.query(Publication).filter(Publication.pmid == record.source_id).first()
        if existing:
            continue

        pub = Publication(
            pmid=record.source_id,
            doi=record.doi,
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
            author = db.query(Author).filter(
                Author.name_normalized == normalize_name(author_data.name)
            ).first()
            if not author:
                author = Author(
                    name=author_data.name,
                    orcid=author_data.orcid,
                    name_normalized=normalize_name(author_data.name),
                )
                db.add(author)
                db.flush()
            db.execute(
                Publication.__table__.metadata.tables["publication_authors"]
                .insert()
                .values(publication_id=pub.id, author_id=author.id, author_position=pos)
            )

            if author_data.affiliation:
                country = extract_country(author_data.affiliation)
                aff = db.query(Affiliation).filter(
                    Affiliation.name_normalized == normalize_name(author_data.affiliation)
                ).first()
                if not aff:
                    aff = Affiliation(
                        name=author_data.affiliation,
                        country=country,
                        name_normalized=normalize_name(author_data.affiliation),
                    )
                    db.add(aff)
                    db.flush()
                if aff not in author.affiliations:
                    author.affiliations.append(aff)

        for term in record.mesh_terms:
            kw = db.query(Keyword).filter(
                Keyword.term_normalized == normalize_name(term),
                Keyword.type == KeywordType.mesh_term,
            ).first()
            if not kw:
                kw = Keyword(
                    term=term,
                    type=KeywordType.mesh_term,
                    term_normalized=normalize_name(term),
                )
                db.add(kw)
                db.flush()
            pub.keywords.append(kw)

        for term in record.keywords:
            kw = db.query(Keyword).filter(
                Keyword.term_normalized == normalize_name(term),
                Keyword.type == KeywordType.author_keyword,
            ).first()
            if not kw:
                kw = Keyword(
                    term=term,
                    type=KeywordType.author_keyword,
                    term_normalized=normalize_name(term),
                )
                db.add(kw)
                db.flush()
            pub.keywords.append(kw)

        persisted += 1

    db.commit()
    return persisted


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


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def run_search(self, query_id: int, source: str = "pubmed"):
    asyncio.run(_run_search(self, query_id, source))


# Keep backward compatibility alias
run_pubmed_search = run_search


async def _run_search(task, query_id: int, source: str):
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
        async for id_batch in adapter.search_paginated(query.query_string):
            all_ids.extend(id_batch)
            task.update_state(
                state="PROGRESS",
                meta={"phase": "search", "ids_found": len(all_ids)},
            )

        query.raw_result_count = len(all_ids)
        db.flush()
        _log_step(db, query_id, step_order=1, phase="search", source=source,
                  action=f"{adapter.methodology_label()} search",
                  records_in=0, records_out=len(all_ids),
                  parameters={"query": query.query_string, "database": source})

        # Phase 2: Fetch + persist in chunks (flat memory)
        persisted = 0
        async for records in adapter.fetch_stream(all_ids, batch_size=200):
            count = _persist_records(db, records, query_id)
            persisted += count
            task.update_state(
                state="PROGRESS",
                meta={"phase": "fetch", "current": persisted, "total": len(all_ids)},
            )

        _log_step(db, query_id, step_order=2, phase="fetch", source=source,
                  action=f"Batch fetch via {adapter.methodology_label()}",
                  records_in=len(all_ids), records_out=persisted,
                  parameters={"batch_size": 200})

        # Phase 3: iCite enrichment (PubMed-sourced records only)
        if source == "pubmed":
            pmids = [rid for rid in all_ids]
            citation_counts = await icite.get_citations(pmids)
            for pmid_str, count in citation_counts.items():
                pub = db.query(Publication).filter(Publication.pmid == pmid_str).first()
                if pub:
                    pub.citation_count = count
            db.commit()
            enriched_count = len(citation_counts)
            _log_step(db, query_id, step_order=3, phase="enrichment", source="icite",
                      action="iCite citation count enrichment",
                      records_in=persisted, records_out=persisted,
                      parameters={"source": "NIH iCite", "enriched": enriched_count,
                                  "missing": persisted - enriched_count})

        query.status = QueryStatus.completed
        query.result_count = persisted
        query.duplicate_count = (query.raw_result_count or 0) - persisted
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
