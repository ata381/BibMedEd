"""Content identity for cached analyses, including enrichment and network inputs."""
import hashlib
import json
from datetime import date

from sqlalchemy.orm import Session, selectinload
from bibmeded.models import Author, Publication, SearchQuery


def corpus_fingerprint(db: Session, project_id: int) -> str:
    query_ids = db.query(SearchQuery.id).filter(SearchQuery.project_id == project_id)
    pubs = (db.query(Publication).filter(Publication.query_id.in_(query_ids), Publication.excluded.is_(False))
            .options(selectinload(Publication.authors).selectinload(Author.affiliations),
                     selectinload(Publication.keywords), selectinload(Publication.journal),
                     selectinload(Publication.outgoing_citations))
            .populate_existing().order_by(Publication.id).all())
    ids = {p.id for p in pubs}
    records = [
        [p.id, p.pmid, p.doi, p.title, p.year, p.citation_count, p.external_references, p.external_ids,
         [p.journal.id, p.journal.name, p.journal.issn] if p.journal else None,
         [[a.id, a.name, a.orcid, sorted([f.id, f.name, f.country] for f in a.affiliations)] for a in p.authors],
         sorted([k.id, k.term, k.type] for k in p.keywords),
         sorted(c.cited_publication_id for c in p.outgoing_citations if c.cited_publication_id in ids)]
        for p in pubs
    ]
    payload = json.dumps([date.today().year, records], sort_keys=True, separators=(",", ":"))
    return "v1:" + hashlib.sha256(payload.encode()).hexdigest()
