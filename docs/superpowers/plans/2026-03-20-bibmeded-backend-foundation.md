# BibMedEd Backend Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend foundation — database models, PubMed search service, iCite citation enrichment, data cleaning pipeline, REST API, and Celery async workers — so the analysis engine and frontend can be built on top.

**Architecture:** Python monorepo with FastAPI backend, PostgreSQL via SQLAlchemy + Alembic migrations, Celery + Redis for async PubMed crawling. Docker Compose orchestrates all services. The backend exposes a REST API that the frontend (Plan 3) will consume.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Celery, Redis, PostgreSQL, httpx (async HTTP), pytest

**Spec:** `docs/superpowers/specs/2026-03-20-bibmeded-design.md`

**Related plans:**
- Plan 2: `2026-03-20-bibmeded-analysis-engine.md` (depends on this plan)
- Plan 3: `2026-03-20-bibmeded-frontend-dashboard.md` (depends on Plans 1 & 2)

---

## File Structure

```
bibmeded/
├── docker-compose.yml                  # PostgreSQL, Redis, API, Celery worker
├── Dockerfile                          # Python backend image
├── pyproject.toml                      # Python dependencies (pip/poetry)
├── alembic.ini                         # Alembic config
├── alembic/
│   ├── env.py
│   └── versions/                       # Migration files
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app factory, CORS, lifespan
│   ├── config.py                       # Settings via pydantic-settings
│   ├── database.py                     # SQLAlchemy engine, session factory
│   ├── models/
│   │   ├── __init__.py                 # Re-exports all models
│   │   ├── project.py                  # SearchProject, SearchQuery
│   │   ├── publication.py              # Publication
│   │   ├── author.py                   # Author, Affiliation, join tables
│   │   ├── journal.py                  # Journal
│   │   ├── keyword.py                  # Keyword, publication_keywords
│   │   ├── citation.py                 # Citation (self-referential)
│   │   └── analysis.py                 # AnalysisRun
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── project.py                  # Pydantic schemas for project CRUD
│   │   ├── publication.py              # Publication response schemas
│   │   ├── search.py                   # Search request/response schemas
│   │   └── analysis.py                 # Analysis request/response schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── projects.py                 # /api/projects CRUD
│   │   ├── search.py                   # /api/search (trigger + status)
│   │   ├── publications.py             # /api/projects/{id}/publications
│   │   └── analysis.py                 # /api/projects/{id}/analysis
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pubmed.py                   # PubMed E-Utilities client
│   │   ├── icite.py                    # NIH iCite API client
│   │   ├── xml_parser.py               # PubMed XML → Publication data
│   │   └── cleaning.py                 # Deduplication, normalization
│   └── workers/
│       ├── __init__.py
│       ├── celery_app.py               # Celery app config
│       └── tasks.py                    # Search + enrichment tasks
├── tests/
│   ├── conftest.py                     # Fixtures: test DB, client, factories
│   ├── fixtures/
│   │   ├── pubmed_response.xml         # Sample PubMed XML (2-3 articles)
│   │   └── icite_response.json         # Sample iCite JSON response
│   ├── test_models.py                  # Model creation, relationships
│   ├── test_pubmed.py                  # PubMed service (mocked HTTP)
│   ├── test_icite.py                   # iCite service (mocked HTTP)
│   ├── test_xml_parser.py              # XML parsing correctness
│   ├── test_cleaning.py                # Dedup + normalization
│   ├── test_routers_projects.py        # Project CRUD API tests
│   ├── test_routers_search.py          # Search trigger API tests
│   └── test_routers_publications.py    # Publication listing API tests
└── frontend/                           # (Plan 3 — empty for now)
    └── .gitkeep
```

---

## Task 1: Project Scaffolding & Docker

**Files:**
- Create: `bibmeded/pyproject.toml`
- Create: `bibmeded/Dockerfile`
- Create: `bibmeded/docker-compose.yml`
- Create: `bibmeded/app/__init__.py`
- Create: `bibmeded/app/main.py`
- Create: `bibmeded/app/config.py`
- Create: `bibmeded/.env.example`
- Create: `bibmeded/.gitignore`

- [ ] **Step 1: Create project directory and pyproject.toml**

```toml
# bibmeded/pyproject.toml
[project]
name = "bibmeded"
version = "0.1.0"
description = "Bibliometric Analysis Platform for Medical Education"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "psycopg2-binary>=2.9.0",
    "pydantic-settings>=2.0.0",
    "redis>=5.0.0",
    "celery[redis]>=5.4.0",
    "httpx>=0.27.0",
    "lxml>=5.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "factory-boy>=3.3.0",
    "pytest-cov>=5.0.0",
]
```

- [ ] **Step 2: Create app/config.py**

```python
# bibmeded/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://bibmeded:bibmeded@localhost:5432/bibmeded"
    redis_url: str = "redis://localhost:6379/0"
    pubmed_api_key: str = ""
    pubmed_rate_limit: float = 3.0  # requests/sec, 10 with API key
    icite_base_url: str = "https://icite.od.nih.gov/api"
    debug: bool = False

    model_config = {"env_prefix": "BIBMEDED_"}


settings = Settings()
```

- [ ] **Step 3: Create app/main.py**

```python
# bibmeded/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="BibMedEd",
        description="Bibliometric Analysis Platform for Medical Education",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 4: Create Dockerfile**

```dockerfile
# bibmeded/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Create docker-compose.yml**

```yaml
# bibmeded/docker-compose.yml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: bibmeded
      POSTGRES_PASSWORD: bibmeded
      POSTGRES_DB: bibmeded
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      BIBMEDED_DATABASE_URL: postgresql://bibmeded:bibmeded@db:5432/bibmeded
      BIBMEDED_REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - .:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build: .
    environment:
      BIBMEDED_DATABASE_URL: postgresql://bibmeded:bibmeded@db:5432/bibmeded
      BIBMEDED_REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis
    command: celery -A app.workers.celery_app worker --loglevel=info

volumes:
  pgdata:
```

- [ ] **Step 6: Create .env.example and .gitignore**

```bash
# bibmeded/.env.example
BIBMEDED_DATABASE_URL=postgresql://bibmeded:bibmeded@localhost:5432/bibmeded
BIBMEDED_REDIS_URL=redis://localhost:6379/0
BIBMEDED_PUBMED_API_KEY=
BIBMEDED_DEBUG=true
```

```gitignore
# bibmeded/.gitignore
__pycache__/
*.pyc
.env
*.egg-info/
.pytest_cache/
.coverage
dist/
node_modules/
.next/
```

- [ ] **Step 7: Create empty __init__.py files**

Create empty `app/__init__.py`.

- [ ] **Step 8: Verify Docker setup**

Run: `cd bibmeded && docker compose up -d db redis`
Expected: PostgreSQL and Redis containers running.

Run: `docker compose ps`
Expected: `db` and `redis` both healthy/running.

- [ ] **Step 9: Verify API starts locally**

Run: `cd bibmeded && pip install -e ".[dev]" && uvicorn app.main:app --port 8000 &`
Run: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`

- [ ] **Step 10: Commit**

```bash
git init
git add -A
git commit -m "feat: project scaffolding with FastAPI, Docker Compose, config"
```

---

## Task 2: Database Models & Migrations

**Files:**
- Create: `bibmeded/app/database.py`
- Create: `bibmeded/app/models/__init__.py`
- Create: `bibmeded/app/models/project.py`
- Create: `bibmeded/app/models/publication.py`
- Create: `bibmeded/app/models/author.py`
- Create: `bibmeded/app/models/journal.py`
- Create: `bibmeded/app/models/keyword.py`
- Create: `bibmeded/app/models/citation.py`
- Create: `bibmeded/app/models/analysis.py`
- Create: `bibmeded/alembic.ini`
- Create: `bibmeded/alembic/env.py`
- Create: `bibmeded/tests/conftest.py`
- Create: `bibmeded/tests/test_models.py`

- [ ] **Step 1: Create app/database.py**

```python
# bibmeded/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Create app/models/project.py**

```python
# bibmeded/app/models/project.py
import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SearchProject(Base):
    __tablename__ = "search_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    queries: Mapped[list["SearchQuery"]] = relationship(back_populates="project")


class QueryStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("search_projects.id"))
    query_string: Mapped[str] = mapped_column(Text)
    database: Mapped[str] = mapped_column(String(50), default="pubmed")
    status: Mapped[QueryStatus] = mapped_column(
        Enum(QueryStatus), default=QueryStatus.pending
    )
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["SearchProject"] = relationship(back_populates="queries")
```

- [ ] **Step 3: Create app/models/publication.py**

```python
# bibmeded/app/models/publication.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pmid: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    publication_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_database: Mapped[str] = mapped_column(String(50), default="pubmed")
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    journal_id: Mapped[int | None] = mapped_column(
        ForeignKey("journals.id"), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    journal: Mapped["Journal | None"] = relationship(back_populates="publications")
    authors: Mapped[list["Author"]] = relationship(
        secondary="publication_authors", back_populates="publications"
    )
    keywords: Mapped[list["Keyword"]] = relationship(
        secondary="publication_keywords", back_populates="publications"
    )
    query_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_queries.id"), nullable=True
    )
```

- [ ] **Step 4: Create app/models/author.py**

```python
# bibmeded/app/models/author.py
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

publication_authors = Table(
    "publication_authors",
    Base.metadata,
    Column("publication_id", Integer, ForeignKey("publications.id"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
    Column("author_position", Integer),
)

author_affiliations = Table(
    "author_affiliations",
    Base.metadata,
    Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
    Column("affiliation_id", Integer, ForeignKey("affiliations.id"), primary_key=True),
)


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    orcid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)

    publications: Mapped[list["Publication"]] = relationship(
        secondary=publication_authors, back_populates="authors"
    )
    affiliations: Mapped[list["Affiliation"]] = relationship(
        secondary=author_affiliations, back_populates="authors"
    )


class Affiliation(Base):
    __tablename__ = "affiliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name_normalized: Mapped[str | None] = mapped_column(String(500), nullable=True)

    authors: Mapped[list["Author"]] = relationship(
        secondary=author_affiliations, back_populates="affiliations"
    )
```

- [ ] **Step 5: Create app/models/journal.py, keyword.py, citation.py, analysis.py**

```python
# bibmeded/app/models/journal.py
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Journal(Base):
    __tablename__ = "journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    issn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    e_issn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name_normalized: Mapped[str | None] = mapped_column(String(500), nullable=True)

    publications: Mapped[list["Publication"]] = relationship(back_populates="journal")
```

```python
# bibmeded/app/models/keyword.py
import enum

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

publication_keywords = Table(
    "publication_keywords",
    Base.metadata,
    Column("publication_id", Integer, ForeignKey("publications.id"), primary_key=True),
    Column("keyword_id", Integer, ForeignKey("keywords.id"), primary_key=True),
)


class KeywordType(str, enum.Enum):
    author_keyword = "author_keyword"
    mesh_term = "mesh_term"


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(255))
    type: Mapped[KeywordType] = mapped_column(Enum(KeywordType))
    term_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)

    publications: Mapped[list["Publication"]] = relationship(
        secondary=publication_keywords, back_populates="keywords"
    )
```

```python
# bibmeded/app/models/citation.py
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Citation(Base):
    __tablename__ = "citations"

    citing_publication_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("publications.id"), primary_key=True
    )
    cited_publication_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("publications.id"), primary_key=True
    )
```

```python
# bibmeded/app/models/analysis.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("search_projects.id"))
    analysis_type: Mapped[str] = mapped_column(String(100))
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    results: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 6: Create app/models/__init__.py**

```python
# bibmeded/app/models/__init__.py
from app.models.analysis import AnalysisRun
from app.models.author import Affiliation, Author, author_affiliations, publication_authors
from app.models.citation import Citation
from app.models.journal import Journal
from app.models.keyword import Keyword, KeywordType, publication_keywords
from app.models.project import QueryStatus, SearchProject, SearchQuery
from app.models.publication import Publication

__all__ = [
    "AnalysisRun",
    "Affiliation",
    "Author",
    "Citation",
    "Journal",
    "Keyword",
    "KeywordType",
    "Publication",
    "QueryStatus",
    "SearchProject",
    "SearchQuery",
    "author_affiliations",
    "publication_authors",
    "publication_keywords",
]
```

- [ ] **Step 7: Initialize Alembic**

Run: `cd bibmeded && alembic init alembic`

Then update `alembic/env.py`:

```python
# bibmeded/alembic/env.py — key changes
from app.config import settings
from app.database import Base
from app.models import *  # noqa: F401, F403 — registers all models

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

- [ ] **Step 8: Generate and run initial migration**

Run: `cd bibmeded && alembic revision --autogenerate -m "initial schema"`
Run: `alembic upgrade head`
Expected: All tables created in PostgreSQL.

- [ ] **Step 9: Write model tests**

```python
# bibmeded/tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import create_app

TEST_DATABASE_URL = "postgresql://bibmeded:bibmeded@localhost:5432/bibmeded_test"

engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)
```

```python
# bibmeded/tests/test_models.py
from datetime import date

from app.models import (
    Author,
    Journal,
    Keyword,
    KeywordType,
    Publication,
    SearchProject,
    SearchQuery,
)


def test_create_project(db):
    project = SearchProject(
        name="AI in Medical Education",
        date_range_start=date(2022, 1, 1),
        date_range_end=date(2025, 6, 30),
    )
    db.add(project)
    db.flush()
    assert project.id is not None
    assert project.name == "AI in Medical Education"


def test_create_publication_with_author(db):
    journal = Journal(name="JMIR Medical Education", issn="2369-3762")
    db.add(journal)
    db.flush()

    pub = Publication(pmid="12345678", title="Test Article", year=2024, journal=journal)
    author = Author(name="Smith, John", name_normalized="smith john")
    pub.authors.append(author)
    db.add(pub)
    db.flush()

    assert pub.id is not None
    assert len(pub.authors) == 1
    assert pub.journal.name == "JMIR Medical Education"


def test_create_keyword(db):
    kw = Keyword(
        term="Artificial Intelligence",
        type=KeywordType.mesh_term,
        term_normalized="artificial intelligence",
    )
    db.add(kw)
    db.flush()
    assert kw.id is not None


def test_project_query_relationship(db):
    project = SearchProject(name="Test Project")
    db.add(project)
    db.flush()

    query = SearchQuery(
        project_id=project.id,
        query_string='"artificial intelligence" AND "medical education"',
    )
    db.add(query)
    db.flush()

    assert len(project.queries) == 1
    assert project.queries[0].query_string == query.query_string
```

- [ ] **Step 10: Run model tests**

Run: `cd bibmeded && pytest tests/test_models.py -v`
Expected: All 4 tests pass.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: database models, Alembic migrations, model tests"
```

---

## Task 3: PubMed Search Service

**Files:**
- Create: `bibmeded/app/services/pubmed.py`
- Create: `bibmeded/app/services/__init__.py`
- Create: `bibmeded/tests/fixtures/pubmed_response.xml`
- Create: `bibmeded/tests/test_pubmed.py`

- [ ] **Step 1: Create test fixture — sample PubMed XML**

```xml
<!-- bibmeded/tests/fixtures/pubmed_response.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE" Owner="NLM">
      <PMID Version="1">38000001</PMID>
      <Article PubModel="Electronic">
        <Journal>
          <ISSN IssnType="Electronic">2369-3762</ISSN>
          <JournalIssue CitedMedium="Internet">
            <Volume>10</Volume>
            <Issue>1</Issue>
            <PubDate><Year>2024</Year></PubDate>
          </JournalIssue>
          <Title>JMIR medical education</Title>
        </Journal>
        <ArticleTitle>Machine Learning in Medical Education: A Systematic Review</ArticleTitle>
        <Abstract>
          <AbstractText>This study reviews the application of machine learning in medical education curricula.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author ValidYN="Y">
            <LastName>Smith</LastName>
            <ForeName>John</ForeName>
            <Identifier Source="ORCID">0000-0001-2345-6789</Identifier>
            <AffiliationInfo>
              <Affiliation>Department of Medical Education, Harvard Medical School, Boston, MA, USA</Affiliation>
            </AffiliationInfo>
          </Author>
          <Author ValidYN="Y">
            <LastName>Chen</LastName>
            <ForeName>Li</ForeName>
            <AffiliationInfo>
              <Affiliation>School of Medicine, Peking University, Beijing, China</Affiliation>
            </AffiliationInfo>
          </Author>
        </AuthorList>
        <ELocationID EIdType="doi" ValidYN="Y">10.2196/12345</ELocationID>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName MajorTopicYN="Y">Artificial Intelligence</DescriptorName>
        </MeshHeading>
        <MeshHeading>
          <DescriptorName MajorTopicYN="Y">Education, Medical</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ReferenceList>
        <Reference>
          <ArticleIdList>
            <ArticleId IdType="pubmed">37000001</ArticleId>
          </ArticleIdList>
        </Reference>
      </ReferenceList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
```

- [ ] **Step 2: Write failing test for PubMed service**

```python
# bibmeded/tests/test_pubmed.py
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.pubmed import PubMedClient


@pytest.fixture
def sample_xml():
    return Path("tests/fixtures/pubmed_response.xml").read_text()


@pytest.fixture
def pubmed_client():
    return PubMedClient(api_key="", rate_limit=10.0)


@pytest.mark.asyncio
async def test_search_returns_pmids(pubmed_client):
    mock_response = AsyncMock()
    mock_response.text = """<?xml version="1.0"?>
    <eSearchResult><Count>2</Count><IdList>
    <Id>38000001</Id><Id>38000002</Id>
    </IdList></eSearchResult>"""
    mock_response.raise_for_status = lambda: None

    with patch.object(pubmed_client._client, "get", return_value=mock_response):
        result = await pubmed_client.search('"artificial intelligence" AND "medical education"')

    assert result.total_count == 2
    assert result.pmids == ["38000001", "38000002"]


@pytest.mark.asyncio
async def test_fetch_records(pubmed_client, sample_xml):
    mock_response = AsyncMock()
    mock_response.text = sample_xml
    mock_response.raise_for_status = lambda: None

    with patch.object(pubmed_client._client, "get", return_value=mock_response):
        records = await pubmed_client.fetch(["38000001"])

    assert len(records) == 1
    assert records[0].pmid == "38000001"
    assert records[0].title == "Machine Learning in Medical Education: A Systematic Review"
    assert len(records[0].authors) == 2
    assert records[0].authors[0].name == "Smith, John"
    assert records[0].doi == "10.2196/12345"
    assert len(records[0].mesh_terms) == 2
    assert len(records[0].references) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd bibmeded && pytest tests/test_pubmed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.pubmed'`

- [ ] **Step 4: Implement PubMed service**

```python
# bibmeded/app/services/__init__.py
```

```python
# bibmeded/app/services/pubmed.py
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

    async def search(
        self,
        query: str,
        retstart: int = 0,
        retmax: int = 10000,
    ) -> SearchResult:
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "xml",
            "retstart": retstart,
            "retmax": retmax,
        }
        if self.api_key:
            params["api_key"] = self.api_key

        response = await self._client.get(ESEARCH_URL, params=params)
        response.raise_for_status()

        root = etree.fromstring(response.text.encode())
        count = int(root.findtext("Count", "0"))
        pmids = [id_el.text for id_el in root.findall(".//IdList/Id") if id_el.text]

        return SearchResult(total_count=count, pmids=pmids)

    async def fetch(self, pmids: list[str]) -> list[PubMedRecord]:
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "full",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        response = await self._client.get(EFETCH_URL, params=params)
        response.raise_for_status()

        return self._parse_records(response.text)

    async def fetch_batched(
        self, pmids: list[str], batch_size: int = 200
    ) -> list[PubMedRecord]:
        all_records = []
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            records = await self.fetch(batch)
            all_records.extend(records)
            await asyncio.sleep(1.0 / self.rate_limit)
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
            abstract = " ".join(
                at.text for at in abstract_parts if at.text
            ) or None

            # Year
            year_text = art.findtext(".//PubDate/Year")
            year = int(year_text) if year_text else None

            # Journal
            journal_name = art.findtext(".//Journal/Title")
            journal_issn = art.findtext(".//Journal/ISSN")

            # DOI
            doi = None
            for eloc in art.findall(".//ELocationID"):
                if eloc.get("EIdType") == "doi":
                    doi = eloc.text
                    break

            # Authors
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

            # MeSH terms
            mesh_terms = [
                desc.text
                for desc in citation.findall(".//MeshHeadingList/MeshHeading/DescriptorName")
                if desc.text
            ]

            # References (PMIDs only)
            references = []
            for ref in article.findall(".//ReferenceList/Reference"):
                for aid in ref.findall(".//ArticleId"):
                    if aid.get("IdType") == "pubmed" and aid.text:
                        references.append(aid.text)

            records.append(
                PubMedRecord(
                    pmid=pmid,
                    title=title,
                    abstract=abstract,
                    doi=doi,
                    year=year,
                    journal_name=journal_name,
                    journal_issn=journal_issn,
                    authors=authors,
                    mesh_terms=mesh_terms,
                    references=references,
                )
            )

        return records

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd bibmeded && pytest tests/test_pubmed.py -v`
Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: PubMed E-Utilities search and fetch service with XML parsing"
```

---

## Task 4: PubMed XML Parser (Thorough Tests)

**Files:**
- Create: `bibmeded/tests/test_xml_parser.py`

- [ ] **Step 1: Write edge case tests for XML parsing**

```python
# bibmeded/tests/test_xml_parser.py
from app.services.pubmed import PubMedClient


def test_parse_missing_abstract():
    xml = """<?xml version="1.0"?>
    <PubmedArticleSet><PubmedArticle>
      <MedlineCitation Status="MEDLINE" Owner="NLM">
        <PMID Version="1">99999999</PMID>
        <Article PubModel="Print">
          <Journal><Title>Test Journal</Title>
            <JournalIssue CitedMedium="Print">
              <PubDate><Year>2023</Year></PubDate>
            </JournalIssue>
          </Journal>
          <ArticleTitle>No Abstract Article</ArticleTitle>
        </Article>
      </MedlineCitation>
      <PubmedData></PubmedData>
    </PubmedArticle></PubmedArticleSet>"""

    client = PubMedClient()
    records = client._parse_records(xml)
    assert len(records) == 1
    assert records[0].abstract is None
    assert records[0].title == "No Abstract Article"
    assert records[0].year == 2023


def test_parse_multiple_authors():
    xml = """<?xml version="1.0"?>
    <PubmedArticleSet><PubmedArticle>
      <MedlineCitation Status="MEDLINE" Owner="NLM">
        <PMID Version="1">11111111</PMID>
        <Article PubModel="Electronic">
          <Journal><Title>Test</Title>
            <JournalIssue CitedMedium="Internet">
              <PubDate><Year>2024</Year></PubDate>
            </JournalIssue>
          </Journal>
          <ArticleTitle>Multi Author</ArticleTitle>
          <AuthorList CompleteYN="Y">
            <Author ValidYN="Y"><LastName>A</LastName><ForeName>B</ForeName></Author>
            <Author ValidYN="Y"><LastName>C</LastName><ForeName>D</ForeName></Author>
            <Author ValidYN="Y"><LastName>E</LastName><ForeName>F</ForeName></Author>
          </AuthorList>
        </Article>
      </MedlineCitation>
      <PubmedData></PubmedData>
    </PubmedArticle></PubmedArticleSet>"""

    client = PubMedClient()
    records = client._parse_records(xml)
    assert len(records[0].authors) == 3
    assert records[0].authors[0].name == "A, B"
    assert records[0].authors[2].name == "E, F"


def test_parse_no_references():
    xml = """<?xml version="1.0"?>
    <PubmedArticleSet><PubmedArticle>
      <MedlineCitation Status="MEDLINE" Owner="NLM">
        <PMID Version="1">22222222</PMID>
        <Article PubModel="Print">
          <Journal><Title>J</Title>
            <JournalIssue CitedMedium="Print">
              <PubDate><Year>2022</Year></PubDate>
            </JournalIssue>
          </Journal>
          <ArticleTitle>No Refs</ArticleTitle>
        </Article>
      </MedlineCitation>
      <PubmedData><ReferenceList></ReferenceList></PubmedData>
    </PubmedArticle></PubmedArticleSet>"""

    client = PubMedClient()
    records = client._parse_records(xml)
    assert records[0].references == []
```

- [ ] **Step 2: Run tests**

Run: `cd bibmeded && pytest tests/test_xml_parser.py -v`
Expected: All 3 tests PASS (parsing is already implemented).

- [ ] **Step 3: Commit**

```bash
git add tests/test_xml_parser.py
git commit -m "test: thorough XML parser edge case tests"
```

---

## Task 5: iCite Citation Enrichment Service

**Files:**
- Create: `bibmeded/app/services/icite.py`
- Create: `bibmeded/tests/fixtures/icite_response.json`
- Create: `bibmeded/tests/test_icite.py`

- [ ] **Step 1: Create test fixture**

Save as `bibmeded/tests/fixtures/icite_response.json`:

```json
{
  "meta": {"total": 2},
  "data": [
    {
      "pmid": 38000001,
      "citation_count": 45,
      "expected_citations_per_year": 8.2,
      "relative_citation_ratio": 2.1,
      "year": 2024
    },
    {
      "pmid": 38000002,
      "citation_count": 12,
      "expected_citations_per_year": 3.1,
      "relative_citation_ratio": 0.8,
      "year": 2023
    }
  ]
}
```

- [ ] **Step 2: Write failing test**

```python
# bibmeded/tests/test_icite.py
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.icite import ICiteClient


@pytest.fixture
def sample_response():
    return json.loads(Path("tests/fixtures/icite_response.json").read_text())


@pytest.fixture
def icite_client():
    return ICiteClient()


@pytest.mark.asyncio
async def test_get_citation_counts(icite_client, sample_response):
    mock_response = AsyncMock()
    mock_response.json = lambda: sample_response
    mock_response.raise_for_status = lambda: None

    with patch.object(icite_client._client, "get", return_value=mock_response):
        result = await icite_client.get_citations(["38000001", "38000002"])

    assert result["38000001"] == 45
    assert result["38000002"] == 12


@pytest.mark.asyncio
async def test_get_citation_counts_empty(icite_client):
    result = await icite_client.get_citations([])
    assert result == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd bibmeded && pytest tests/test_icite.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.icite'`

- [ ] **Step 4: Implement iCite service**

```python
# bibmeded/app/services/icite.py
import httpx

from app.config import settings

ICITE_API_URL = settings.icite_base_url + "/pubs"


class ICiteClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_citations(self, pmids: list[str]) -> dict[str, int]:
        """Returns a dict of {pmid: citation_count}."""
        if not pmids:
            return {}

        results = {}
        # iCite accepts up to 1000 PMIDs per request
        for i in range(0, len(pmids), 1000):
            batch = pmids[i : i + 1000]
            response = await self._client.get(
                ICITE_API_URL,
                params={"pmids": ",".join(batch), "format": "json"},
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("data", []):
                pmid = str(item["pmid"])
                results[pmid] = item.get("citation_count", 0)

        return results

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd bibmeded && pytest tests/test_icite.py -v`
Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: NIH iCite citation count enrichment service"
```

---

## Task 6: Data Cleaning Service

**Files:**
- Create: `bibmeded/app/services/cleaning.py`
- Create: `bibmeded/tests/test_cleaning.py`

- [ ] **Step 1: Write failing test**

```python
# bibmeded/tests/test_cleaning.py
from app.services.cleaning import normalize_name, deduplicate_records, extract_country
from app.services.pubmed import PubMedAuthor, PubMedRecord


def test_normalize_name():
    assert normalize_name("Smith, John A.") == "smith john a"
    assert normalize_name("  Chen,  Li  ") == "chen li"
    assert normalize_name("O'Brien, Mary") == "obrien mary"


def test_extract_country():
    assert extract_country("Department of Medicine, Harvard Medical School, Boston, MA, USA") == "USA"
    assert extract_country("Peking University, Beijing, China") == "China"
    assert extract_country("Unknown Affiliation") is None


def test_deduplicate_by_pmid():
    records = [
        PubMedRecord(pmid="111", title="First"),
        PubMedRecord(pmid="222", title="Second"),
        PubMedRecord(pmid="111", title="First Duplicate"),
    ]
    deduped = deduplicate_records(records)
    assert len(deduped) == 2
    assert {r.pmid for r in deduped} == {"111", "222"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd bibmeded && pytest tests/test_cleaning.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement cleaning service**

```python
# bibmeded/app/services/cleaning.py
import re

from app.services.pubmed import PubMedRecord

# Common country names found at the end of affiliation strings
COUNTRIES = [
    "USA", "United States", "China", "United Kingdom", "UK", "Germany", "Japan",
    "Canada", "Australia", "France", "Italy", "Spain", "South Korea", "India",
    "Brazil", "Netherlands", "Turkey", "Sweden", "Switzerland", "Iran",
    "Taiwan", "Saudi Arabia", "Singapore", "Belgium", "Denmark", "Norway",
    "Finland", "Austria", "Poland", "Israel", "Portugal", "Ireland",
    "New Zealand", "Greece", "Czech Republic", "Thailand", "Malaysia",
    "Mexico", "Egypt", "South Africa", "Pakistan", "Colombia", "Chile",
    "Argentina", "Indonesia", "Nigeria", "Russia", "Romania", "Hungary",
]

# Normalize common variants
COUNTRY_ALIASES = {
    "United States": "USA",
    "United States of America": "USA",
    "U.S.A.": "USA",
    "United Kingdom": "UK",
    "England": "UK",
    "Scotland": "UK",
    "Wales": "UK",
    "Republic of Korea": "South Korea",
    "Korea": "South Korea",
    "Peoples Republic of China": "China",
    "P.R. China": "China",
}


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def extract_country(affiliation: str) -> str | None:
    """Extract country from the end of an affiliation string."""
    if not affiliation:
        return None

    # Clean up trailing period and whitespace
    aff = affiliation.strip().rstrip(".")

    # Check aliases first (longer matches)
    for alias, canonical in COUNTRY_ALIASES.items():
        if aff.lower().endswith(alias.lower()):
            return canonical

    # Check direct country names
    for country in COUNTRIES:
        if aff.endswith(country) or aff.endswith(country + "."):
            return country

    return None


def deduplicate_records(records: list[PubMedRecord]) -> list[PubMedRecord]:
    """Remove duplicate records by PMID, keeping the first occurrence."""
    seen = set()
    unique = []
    for record in records:
        if record.pmid not in seen:
            seen.add(record.pmid)
            unique.append(record)
    return unique
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd bibmeded && pytest tests/test_cleaning.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: data cleaning service — name normalization, country extraction, dedup"
```

---

## Task 7: Pydantic Schemas

**Files:**
- Create: `bibmeded/app/schemas/__init__.py`
- Create: `bibmeded/app/schemas/project.py`
- Create: `bibmeded/app/schemas/publication.py`
- Create: `bibmeded/app/schemas/search.py`

- [ ] **Step 1: Create schemas**

```python
# bibmeded/app/schemas/__init__.py
```

```python
# bibmeded/app/schemas/project.py
from datetime import date, datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    date_range_start: date | None
    date_range_end: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    publication_count: int = 0

    model_config = {"from_attributes": True}
```

```python
# bibmeded/app/schemas/publication.py
from pydantic import BaseModel


class AuthorResponse(BaseModel):
    id: int
    name: str
    orcid: str | None

    model_config = {"from_attributes": True}


class PublicationResponse(BaseModel):
    id: int
    pmid: str
    doi: str | None
    title: str
    abstract: str | None
    year: int | None
    publication_type: str | None
    citation_count: int | None
    journal_name: str | None = None
    authors: list[AuthorResponse] = []

    model_config = {"from_attributes": True}


class PublicationListResponse(BaseModel):
    total: int
    items: list[PublicationResponse]
```

```python
# bibmeded/app/schemas/search.py
from pydantic import BaseModel


class SearchRequest(BaseModel):
    query_string: str
    database: str = "pubmed"


class SearchStatusResponse(BaseModel):
    query_id: int
    status: str
    result_count: int | None
    progress: float | None = None  # 0.0 - 1.0

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "feat: Pydantic request/response schemas"
```

---

## Task 8: Project CRUD API Router

**Files:**
- Create: `bibmeded/app/routers/__init__.py`
- Create: `bibmeded/app/routers/projects.py`
- Create: `bibmeded/tests/test_routers_projects.py`

- [ ] **Step 1: Write failing test**

```python
# bibmeded/tests/test_routers_projects.py
def test_create_project(client):
    response = client.post("/api/projects", json={
        "name": "AI in Medical Education",
        "description": "Bibliometric analysis",
        "date_range_start": "2022-01-01",
        "date_range_end": "2025-06-30",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "AI in Medical Education"
    assert data["id"] is not None


def test_list_projects(client):
    client.post("/api/projects", json={"name": "Project 1"})
    client.post("/api/projects", json={"name": "Project 2"})

    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_project(client):
    create = client.post("/api/projects", json={"name": "Test"})
    project_id = create.json()["id"]

    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test"


def test_get_project_not_found(client):
    response = client.get("/api/projects/99999")
    assert response.status_code == 404


def test_delete_project(client):
    create = client.post("/api/projects", json={"name": "To Delete"})
    project_id = create.json()["id"]

    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 204

    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd bibmeded && pytest tests/test_routers_projects.py -v`
Expected: FAIL — 404 on all routes (router not registered).

- [ ] **Step 3: Implement projects router**

```python
# bibmeded/app/routers/__init__.py
```

```python
# bibmeded/app/routers/projects.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SearchProject
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectResponse)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = SearchProject(**body.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(SearchProject).order_by(SearchProject.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
```

- [ ] **Step 4: Register router in main.py**

Update `app/main.py` to include:

```python
from app.routers import projects

# Inside create_app(), after CORS middleware:
app.include_router(projects.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd bibmeded && pytest tests/test_routers_projects.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: project CRUD API endpoints"
```

---

## Task 9: Search Trigger API + Celery Workers

**Files:**
- Create: `bibmeded/app/workers/celery_app.py`
- Create: `bibmeded/app/workers/__init__.py`
- Create: `bibmeded/app/workers/tasks.py`
- Create: `bibmeded/app/routers/search.py`
- Create: `bibmeded/tests/test_routers_search.py`

- [ ] **Step 1: Create Celery app**

```python
# bibmeded/app/workers/__init__.py
```

```python
# bibmeded/app/workers/celery_app.py
from celery import Celery

from app.config import settings

celery_app = Celery(
    "bibmeded",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
```

- [ ] **Step 2: Create search task**

```python
# bibmeded/app/workers/tasks.py
import asyncio
from datetime import datetime

from app.database import SessionLocal
from app.models import (
    Affiliation,
    Author,
    Journal,
    Keyword,
    KeywordType,
    Publication,
    SearchQuery,
    QueryStatus,
)
from app.services.cleaning import deduplicate_records, extract_country, normalize_name
from app.services.icite import ICiteClient
from app.services.pubmed import PubMedClient
from app.workers.celery_app import celery_app


@celery_app.task(bind=True)
def run_pubmed_search(self, query_id: int):
    """Fetch PubMed results, clean, enrich with iCite, store in DB."""
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

        # Step 1: Search PubMed
        search_result = await pubmed.search(query.query_string)
        total = search_result.total_count
        pmids = search_result.pmids

        # Handle >10k results via date-slicing (simplified: just cap for now)
        task.update_state(state="PROGRESS", meta={"current": 0, "total": total})

        # Step 2: Fetch records in batches
        records = await pubmed.fetch_batched(pmids, batch_size=200)
        records = deduplicate_records(records)

        # Step 3: Get citation counts from iCite
        all_pmids = [r.pmid for r in records]
        citation_counts = await icite.get_citations(all_pmids)

        # Step 4: Store in database
        for i, record in enumerate(records):
            # Journal (get or create)
            journal = None
            if record.journal_name:
                journal = (
                    db.query(Journal)
                    .filter(Journal.name == record.journal_name)
                    .first()
                )
                if not journal:
                    journal = Journal(
                        name=record.journal_name,
                        issn=record.journal_issn,
                        name_normalized=normalize_name(record.journal_name),
                    )
                    db.add(journal)
                    db.flush()

            # Publication
            existing = db.query(Publication).filter(Publication.pmid == record.pmid).first()
            if existing:
                continue

            pub = Publication(
                pmid=record.pmid,
                doi=record.doi,
                title=record.title,
                abstract=record.abstract,
                year=record.year,
                source_database="pubmed",
                citation_count=citation_counts.get(record.pmid),
                journal_id=journal.id if journal else None,
                query_id=query_id,
            )
            db.add(pub)
            db.flush()

            # Authors
            for pos, author_data in enumerate(record.authors):
                author = (
                    db.query(Author)
                    .filter(Author.name_normalized == normalize_name(author_data.name))
                    .first()
                )
                if not author:
                    author = Author(
                        name=author_data.name,
                        orcid=author_data.orcid,
                        name_normalized=normalize_name(author_data.name),
                    )
                    db.add(author)
                    db.flush()

                # Link publication-author
                db.execute(
                    pub.__class__.__table__
                    .metadata.tables["publication_authors"]
                    .insert()
                    .values(
                        publication_id=pub.id,
                        author_id=author.id,
                        author_position=pos,
                    )
                )

                # Affiliation
                if author_data.affiliation:
                    country = extract_country(author_data.affiliation)
                    aff = (
                        db.query(Affiliation)
                        .filter(
                            Affiliation.name_normalized
                            == normalize_name(author_data.affiliation)
                        )
                        .first()
                    )
                    if not aff:
                        aff = Affiliation(
                            name=author_data.affiliation,
                            country=country,
                            name_normalized=normalize_name(author_data.affiliation),
                        )
                        db.add(aff)
                        db.flush()

            # Keywords (MeSH + author)
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

            if (i + 1) % 50 == 0:
                db.commit()
                task.update_state(
                    state="PROGRESS", meta={"current": i + 1, "total": len(records)}
                )

        query.status = QueryStatus.completed
        query.result_count = len(records)
        query.executed_at = datetime.utcnow()
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
```

- [ ] **Step 3: Create search router**

```python
# bibmeded/app/routers/search.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SearchProject, SearchQuery
from app.schemas.search import SearchRequest, SearchStatusResponse
from app.workers.tasks import run_pubmed_search

router = APIRouter(prefix="/api/projects/{project_id}/search", tags=["search"])


@router.post("", status_code=202, response_model=SearchStatusResponse)
def trigger_search(
    project_id: int, body: SearchRequest, db: Session = Depends(get_db)
):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = SearchQuery(
        project_id=project_id,
        query_string=body.query_string,
        database=body.database,
    )
    db.add(query)
    db.commit()
    db.refresh(query)

    # Dispatch Celery task
    run_pubmed_search.delay(query.id)

    return SearchStatusResponse(
        query_id=query.id,
        status=query.status.value,
        result_count=None,
    )


@router.get("/{query_id}", response_model=SearchStatusResponse)
def get_search_status(
    project_id: int, query_id: int, db: Session = Depends(get_db)
):
    query = db.get(SearchQuery, query_id)
    if not query or query.project_id != project_id:
        raise HTTPException(status_code=404, detail="Search query not found")

    return SearchStatusResponse(
        query_id=query.id,
        status=query.status.value,
        result_count=query.result_count,
    )
```

- [ ] **Step 4: Register search router in main.py**

Update `app/main.py`:

```python
from app.routers import projects, search

app.include_router(projects.router)
app.include_router(search.router)
```

- [ ] **Step 5: Write API test (mocking Celery)**

```python
# bibmeded/tests/test_routers_search.py
from unittest.mock import patch

from app.models import SearchProject


def test_trigger_search(client, db):
    project = SearchProject(name="Test")
    db.add(project)
    db.commit()
    db.refresh(project)

    with patch("app.routers.search.run_pubmed_search") as mock_task:
        mock_task.delay.return_value = None
        response = client.post(
            f"/api/projects/{project.id}/search",
            json={"query_string": '"AI" AND "medical education"'},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    assert data["query_id"] is not None
    mock_task.delay.assert_called_once()


def test_get_search_status(client, db):
    project = SearchProject(name="Test")
    db.add(project)
    db.commit()
    db.refresh(project)

    with patch("app.routers.search.run_pubmed_search") as mock_task:
        mock_task.delay.return_value = None
        create = client.post(
            f"/api/projects/{project.id}/search",
            json={"query_string": "test"},
        )

    query_id = create.json()["query_id"]
    response = client.get(f"/api/projects/{project.id}/search/{query_id}")
    assert response.status_code == 200
    assert response.json()["query_id"] == query_id
```

- [ ] **Step 6: Run tests**

Run: `cd bibmeded && pytest tests/test_routers_search.py -v`
Expected: Both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: search trigger API, Celery workers for PubMed fetch + iCite enrichment"
```

---

## Task 10: Publications API Router

**Files:**
- Create: `bibmeded/app/routers/publications.py`
- Create: `bibmeded/tests/test_routers_publications.py`

- [ ] **Step 1: Write failing test**

```python
# bibmeded/tests/test_routers_publications.py
from app.models import Author, Journal, Publication, SearchProject, SearchQuery


def test_list_publications(client, db):
    project = SearchProject(name="Test")
    db.add(project)
    db.flush()

    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()

    journal = Journal(name="Test Journal")
    db.add(journal)
    db.flush()

    pub = Publication(
        pmid="11111111",
        title="Test Paper",
        year=2024,
        journal_id=journal.id,
        query_id=query.id,
    )
    author = Author(name="Smith, John")
    pub.authors.append(author)
    db.add(pub)
    db.commit()

    response = client.get(f"/api/projects/{project.id}/publications")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["items"][0]["title"] == "Test Paper"


def test_list_publications_with_sort(client, db):
    project = SearchProject(name="Sort Test")
    db.add(project)
    db.flush()

    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()

    for i, year in enumerate([2023, 2024, 2022]):
        pub = Publication(
            pmid=f"sort{i}", title=f"Paper {i}", year=year, query_id=query.id
        )
        db.add(pub)
    db.commit()

    response = client.get(
        f"/api/projects/{project.id}/publications?sort_by=year&order=asc"
    )
    years = [p["year"] for p in response.json()["items"]]
    assert years == sorted(years)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd bibmeded && pytest tests/test_routers_publications.py -v`
Expected: FAIL — 404 (router not registered).

- [ ] **Step 3: Implement publications router**

```python
# bibmeded/app/routers/publications.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Publication, SearchProject, SearchQuery
from app.schemas.publication import PublicationListResponse, PublicationResponse

router = APIRouter(
    prefix="/api/projects/{project_id}/publications", tags=["publications"]
)


@router.get("", response_model=PublicationListResponse)
def list_publications(
    project_id: int,
    sort_by: str = Query("year", enum=["year", "title", "citation_count"]),
    order: str = Query("desc", enum=["asc", "desc"]),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    project = db.get(SearchProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return PublicationListResponse(total=0, items=[])

    base_query = (
        db.query(Publication)
        .options(joinedload(Publication.authors), joinedload(Publication.journal))
        .filter(Publication.query_id.in_(query_ids))
    )

    total = base_query.count()

    sort_col = getattr(Publication, sort_by, Publication.year)
    if order == "desc":
        sort_col = sort_col.desc()
    else:
        sort_col = sort_col.asc()

    publications = base_query.order_by(sort_col).offset(offset).limit(limit).all()

    items = []
    for pub in publications:
        item = PublicationResponse(
            id=pub.id,
            pmid=pub.pmid,
            doi=pub.doi,
            title=pub.title,
            abstract=pub.abstract,
            year=pub.year,
            publication_type=pub.publication_type,
            citation_count=pub.citation_count,
            journal_name=pub.journal.name if pub.journal else None,
            authors=[
                {"id": a.id, "name": a.name, "orcid": a.orcid} for a in pub.authors
            ],
        )
        items.append(item)

    return PublicationListResponse(total=total, items=items)
```

- [ ] **Step 4: Register in main.py**

Update `app/main.py`:

```python
from app.routers import projects, search, publications

app.include_router(projects.router)
app.include_router(search.router)
app.include_router(publications.router)
```

- [ ] **Step 5: Run tests**

Run: `cd bibmeded && pytest tests/test_routers_publications.py -v`
Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: publications listing API with sorting and pagination"
```

---

## Task 11: Integration Smoke Test

**Files:**
- None new — verify full stack works together.

- [ ] **Step 1: Run full test suite**

Run: `cd bibmeded && pytest tests/ -v --tb=short`
Expected: All tests pass (models, pubmed, icite, xml_parser, cleaning, routers).

- [ ] **Step 2: Verify Docker Compose boots all services**

Run: `cd bibmeded && docker compose up -d`
Run: `docker compose ps`
Expected: `db`, `redis`, `api`, `worker` all running.

Run: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`

Run: `curl http://localhost:8000/api/projects`
Expected: `[]` (empty list)

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "chore: integration smoke test verified"
```

---

## Summary

After completing all 11 tasks, you have:

- **FastAPI backend** with health check and CORS
- **PostgreSQL database** with all models and Alembic migrations
- **PubMed service** — search (ESearch) + fetch (EFetch) + XML parsing
- **iCite service** — citation count enrichment
- **Data cleaning** — name normalization, country extraction, deduplication
- **Celery worker** — async PubMed fetch + store pipeline
- **REST API** — project CRUD, search trigger + status, publications listing
- **Docker Compose** — all services orchestrated
- **Test suite** — unit + integration tests covering all services

**Next:** Plan 2 (Analysis Engine) builds the 6 bibliometric analysis modules on top of this foundation.
