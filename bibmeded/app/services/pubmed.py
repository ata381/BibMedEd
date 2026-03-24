import asyncio
from dataclasses import dataclass, field
import httpx
from lxml import etree

@dataclass
class PubMedAuthor:
    name: str
    orcid: str | None = None
    affiliation: str | None = None

@dataclass
class SearchResult:
    total_count: int
    pmids: list[str]

@dataclass
class PubMedRecord:
    pmid: str
    title: str
    abstract: str | None = None
    doi: str | None = None
    year: int | None = None
    journal_name: str | None = None
    journal_issn: str | None = None
    publication_type: str | None = None
    authors: list[PubMedAuthor] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    author_keywords: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)  # PMIDs of referenced papers

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

class PubMedClient:
    def __init__(self, api_key: str = "", rate_limit: float = 3.0):
        self.api_key = api_key
        self.rate_limit = rate_limit
        self._client = httpx.AsyncClient(timeout=30.0)
        self._last_request_time: float = 0.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def _throttle(self) -> None:
        """Enforce rate limiting between consecutive API requests."""
        now = asyncio.get_event_loop().time()
        min_interval = 1.0 / self.rate_limit
        elapsed = now - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def search(self, query: str, retstart: int = 0, retmax: int = 10000) -> SearchResult:
        params = {"db": "pubmed", "term": query, "retmode": "xml", "retstart": retstart, "retmax": retmax}
        if self.api_key:
            params["api_key"] = self.api_key
        await self._throttle()
        response = await self._client.get(ESEARCH_URL, params=params)
        response.raise_for_status()
        root = etree.fromstring(response.text.encode())
        count = int(root.findtext("Count", "0"))
        pmids = [id_el.text for id_el in root.findall(".//IdList/Id") if id_el.text]
        return SearchResult(total_count=count, pmids=pmids)

    async def fetch(self, pmids: list[str]) -> list[PubMedRecord]:
        params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "full"}
        if self.api_key:
            params["api_key"] = self.api_key
        await self._throttle()
        response = await self._client.get(EFETCH_URL, params=params)
        response.raise_for_status()
        return self._parse_records(response.text)

    async def fetch_batched(self, pmids: list[str], batch_size: int = 200) -> list[PubMedRecord]:
        all_records = []
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i:i + batch_size]
            records = await self.fetch(batch)
            all_records.extend(records)
        return all_records

    def _parse_records(self, xml_text: str) -> list[PubMedRecord]:
        root = etree.fromstring(xml_text.encode())
        records = []
        for article in root.findall(".//PubmedArticle"):
            citation = article.find("MedlineCitation")
            if citation is None:
                continue
            pmid = citation.findtext("PMID", "")
            art = citation.find("Article")
            if art is None:
                continue
            title = art.findtext("ArticleTitle", "")
            abstract_parts = art.findall(".//AbstractText")
            abstract = " ".join(at.text for at in abstract_parts if at.text) or None
            year_text = art.findtext(".//PubDate/Year")
            year = int(year_text) if year_text else None
            journal_name = art.findtext(".//Journal/Title")
            journal_issn = art.findtext(".//Journal/ISSN")
            doi = None
            for eloc in art.findall(".//ELocationID"):
                if eloc.get("EIdType") == "doi":
                    doi = eloc.text
                    break
            authors = []
            for auth_el in art.findall(".//AuthorList/Author"):
                last = auth_el.findtext("LastName", "")
                first = auth_el.findtext("ForeName", "")
                name = f"{last}, {first}" if last else first
                orcid = None
                for ident in auth_el.findall("Identifier"):
                    if ident.get("Source") == "ORCID":
                        orcid = ident.text
                aff_el = auth_el.find(".//AffiliationInfo/Affiliation")
                affiliation = aff_el.text if aff_el is not None else None
                authors.append(PubMedAuthor(name=name, orcid=orcid, affiliation=affiliation))
            pub_types = art.findall(".//PublicationTypeList/PublicationType")
            publication_type = pub_types[0].text if pub_types and pub_types[0].text else None
            author_keywords = [
                kw.text for kw in art.findall(".//KeywordList/Keyword") if kw.text
            ]
            mesh_terms = [desc.text for desc in citation.findall(".//MeshHeadingList/MeshHeading/DescriptorName") if desc.text]
            references = []
            for ref in article.findall(".//ReferenceList/Reference"):
                for aid in ref.findall(".//ArticleId"):
                    if aid.get("IdType") == "pubmed" and aid.text:
                        references.append(aid.text)
            records.append(PubMedRecord(
                pmid=pmid, title=title, abstract=abstract, doi=doi, year=year,
                journal_name=journal_name, journal_issn=journal_issn,
                publication_type=publication_type,
                authors=authors, mesh_terms=mesh_terms,
                author_keywords=author_keywords, references=references,
            ))
        return records

    async def close(self):
        await self._client.aclose()
