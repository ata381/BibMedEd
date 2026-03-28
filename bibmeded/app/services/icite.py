import httpx
from app.config import settings

ICITE_API_URL = settings.icite_base_url + "/pubs"

class ICiteClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_citations(self, pmids: list[str]) -> dict[str, int]:
        if not pmids:
            return {}
        results = {}
        for i in range(0, len(pmids), 1000):
            batch = pmids[i:i + 1000]
            response = await self._client.get(ICITE_API_URL, params={"pmids": ",".join(batch), "format": "json"})
            response.raise_for_status()
            data = response.json()
            for item in data.get("data", []):
                pmid = str(item["pmid"])
                results[pmid] = item.get("citation_count", 0)
        return results

    async def close(self):
        await self._client.aclose()
