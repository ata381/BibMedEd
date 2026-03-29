from app.adapters.base import BaseSourceAdapter, RawAuthor, RawRecord, SearchResponse
from app.services.pubmed import PubMedClient, PubMedRecord


class PubMedAdapter(BaseSourceAdapter):
    name = "pubmed"
    display_name = "PubMed"
    requires_api_key = False

    def __init__(self, api_key: str = "", rate_limit: float = 3.0):
        self._client = PubMedClient(api_key=api_key, rate_limit=rate_limit)

    async def search(self, query: str, **kwargs) -> SearchResponse:
        result = await self._client.search(query)
        return SearchResponse(total_count=result.total_count, ids=result.pmids)

    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        records = await self._client.fetch(ids)
        return [self._to_raw(r) for r in records]

    def _to_raw(self, r: PubMedRecord) -> RawRecord:
        external_ids: dict[str, str] = {"pmid": r.pmid}
        if r.doi:
            external_ids["doi"] = r.doi
        return RawRecord(
            source_id=r.pmid,
            source_database="pubmed",
            title=r.title,
            abstract=r.abstract,
            doi=r.doi,
            year=r.year,
            journal_name=r.journal_name,
            journal_issn=r.journal_issn,
            publication_type=r.publication_type,
            authors=[
                RawAuthor(name=a.name, orcid=a.orcid, affiliation=a.affiliation)
                for a in r.authors
            ],
            mesh_terms=r.mesh_terms,
            keywords=r.author_keywords,
            references=r.references,
            external_ids=external_ids,
        )

    def methodology_label(self) -> str:
        return "PubMed E-Utilities"

    async def close(self) -> None:
        await self._client.close()
