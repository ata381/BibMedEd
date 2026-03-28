import asyncio
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models import (Affiliation, Author, Journal, Keyword, KeywordType, Publication, SearchQuery, QueryStatus)
from app.services.cleaning import deduplicate_records, extract_country, normalize_name
from app.services.icite import ICiteClient
from app.services.pubmed import PubMedClient
from app.workers.celery_app import celery_app

@celery_app.task(bind=True)
def run_pubmed_search(self, query_id: int):
    asyncio.run(_run_search(self, query_id))

async def _run_search(task, query_id: int):
    db = SessionLocal()
    pubmed = PubMedClient()
    icite = ICiteClient()
    try:
        query = db.get(SearchQuery, query_id)
        if not query:
            return
        query.status = QueryStatus.running
        db.commit()

        search_result = await pubmed.search(query.query_string)
        pmids = search_result.pmids
        task.update_state(state="PROGRESS", meta={"current": 0, "total": search_result.total_count})

        records = await pubmed.fetch_batched(pmids, batch_size=200)
        records = deduplicate_records(records)

        all_pmids = [r.pmid for r in records]
        citation_counts = await icite.get_citations(all_pmids)

        for i, record in enumerate(records):
            journal = None
            if record.journal_name:
                journal = db.query(Journal).filter(Journal.name == record.journal_name).first()
                if not journal:
                    journal = Journal(name=record.journal_name, issn=record.journal_issn, name_normalized=normalize_name(record.journal_name))
                    db.add(journal)
                    db.flush()

            existing = db.query(Publication).filter(Publication.pmid == record.pmid).first()
            if existing:
                continue

            pub = Publication(pmid=record.pmid, doi=record.doi, title=record.title, abstract=record.abstract,
                year=record.year, source_database="pubmed", citation_count=citation_counts.get(record.pmid),
                journal_id=journal.id if journal else None, query_id=query_id)
            db.add(pub)
            db.flush()

            for pos, author_data in enumerate(record.authors):
                author = db.query(Author).filter(Author.name_normalized == normalize_name(author_data.name)).first()
                if not author:
                    author = Author(name=author_data.name, orcid=author_data.orcid, name_normalized=normalize_name(author_data.name))
                    db.add(author)
                    db.flush()
                db.execute(
                    Publication.__table__.metadata.tables["publication_authors"].insert().values(
                        publication_id=pub.id, author_id=author.id, author_position=pos))

                if author_data.affiliation:
                    country = extract_country(author_data.affiliation)
                    aff = db.query(Affiliation).filter(Affiliation.name_normalized == normalize_name(author_data.affiliation)).first()
                    if not aff:
                        aff = Affiliation(name=author_data.affiliation, country=country, name_normalized=normalize_name(author_data.affiliation))
                        db.add(aff)
                        db.flush()
                    if aff not in author.affiliations:
                        author.affiliations.append(aff)

            for term in record.mesh_terms:
                kw = db.query(Keyword).filter(Keyword.term_normalized == normalize_name(term), Keyword.type == KeywordType.mesh_term).first()
                if not kw:
                    kw = Keyword(term=term, type=KeywordType.mesh_term, term_normalized=normalize_name(term))
                    db.add(kw)
                    db.flush()
                pub.keywords.append(kw)

            if (i + 1) % 50 == 0:
                db.commit()
                task.update_state(state="PROGRESS", meta={"current": i + 1, "total": len(records)})

        query.status = QueryStatus.completed
        query.result_count = len(records)
        query.executed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        query = db.get(SearchQuery, query_id)
        if query:
            query.status = QueryStatus.failed
            db.commit()
        raise e
    finally:
        await pubmed.close()
        await icite.close()
        db.close()
