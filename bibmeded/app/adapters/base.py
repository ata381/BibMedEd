from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field


@dataclass
class RawAuthor:
    name: str
    orcid: str | None = None
    affiliation: str | None = None


@dataclass
class RawRecord:
    """Universal intermediate format — all adapters map to this."""
    source_id: str
    source_database: str
    title: str
    abstract: str | None = None
    doi: str | None = None
    year: int | None = None
    journal_name: str | None = None
    journal_issn: str | None = None
    publication_type: str | None = None
    authors: list[RawAuthor] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    external_ids: dict[str, str] = field(default_factory=dict)


@dataclass
class SearchResponse:
    total_count: int
    ids: list[str]


class BaseSourceAdapter(ABC):
    name: str
    display_name: str
    requires_api_key: bool

    @abstractmethod
    async def search(self, query: str, **kwargs) -> SearchResponse:
        """Return total_count + first page of IDs."""
        ...

    async def search_paginated(self, query: str, **kwargs) -> AsyncGenerator[list[str], None]:
        """Yield ID batches. Default: single yield from search()."""
        result = await self.search(query, **kwargs)
        yield result.ids

    @abstractmethod
    async def fetch(self, ids: list[str]) -> list[RawRecord]:
        """Fetch a single batch of records by ID."""
        ...

    async def fetch_stream(self, ids: list[str], batch_size: int = 200) -> AsyncGenerator[list[RawRecord], None]:
        """Yield record chunks for flat memory. Default: slice + fetch()."""
        for i in range(0, len(ids), batch_size):
            yield await self.fetch(ids[i:i + batch_size])

    def methodology_label(self) -> str:
        """Human-readable source description for methodology log."""
        return f"{self.display_name} API"

    async def close(self) -> None:
        """Clean up HTTP clients. Override if adapter holds resources."""
        pass
