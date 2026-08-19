from datetime import date, datetime, timezone
from threading import Lock

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.base import RawAuthor, RawRecord
from app.models import Publication, QueryStatus, SearchProject, SearchQuery
from app.models.methodology import MethodologyStep
from app.workers.tasks import _persist_records


SAMPLE_PROJECT_NAME = "AI in Medical Education — Sample Project"
SAMPLE_PROJECT_ID = -381_000_001
SAMPLE_QUERY_STRING = "Bundled synthetic demonstration corpus"
SAMPLE_PROJECT_DESCRIPTION = (
    "A synthetic demonstration corpus bundled with BibMedEd. Explore every analysis, "
    "screening, PRISMA, and export workflow without calling an external database."
)
_sample_creation_lock = Lock()


def _author(name: str, institution: str, country: str) -> RawAuthor:
    return RawAuthor(name=name, affiliation=f"{institution}, {country}")


def _sample_records() -> list[RawRecord]:
    authors = {
        "garcia": ("Elena Garcia Sample", "Sample Center for Health Professions Education, Utrecht University", "Netherlands"),
        "chen": ("Marcus Chen Sample", "Sample Department of Medical Education, University of Toronto", "Canada"),
        "okafor": ("Amina Okafor Sample", "Sample Faculty of Health Sciences, University of Cape Town", "South Africa"),
        "demir": ("Sofia Demir Sample", "Sample Department of Medical Education, Hacettepe University", "Turkey"),
        "patel": ("James Patel Sample", "Sample Institute for Medical Education, University College London", "UK"),
        "kim": ("Hana Kim Sample", "Sample Seoul National University College of Medicine", "South Korea"),
        "santos": ("Luis Santos Sample", "Sample School of Medicine, University of Sao Paulo", "Brazil"),
        "johnson": ("Mia Johnson Sample", "Sample School of Medicine, University of Michigan", "USA"),
    }
    specifications = (
        ("sample-001", 2018, "Simulation-based feedback in undergraduate clinical training", "Medical Education Practice", 64, ("garcia", "patel"), ("simulation", "feedback", "clinical skills"), ()),
        ("sample-002", 2019, "Learning analytics for early identification of struggling medical students", "Digital Health Education", 51, ("chen", "johnson"), ("learning analytics", "assessment", "student support"), ()),
        ("sample-003", 2019, "Faculty perspectives on artificial intelligence in health professions education", "Medical Teacher Insights", 39, ("okafor", "demir"), ("artificial intelligence", "faculty development", "medical education"), ("sample-001",)),
        ("sample-004", 2020, "Virtual patients for diagnostic reasoning: a multi-institutional study", "Medical Education Practice", 47, ("garcia", "chen", "kim"), ("virtual patients", "diagnostic reasoning", "simulation"), ("sample-001", "sample-002")),
        ("sample-005", 2020, "Equity and access in digitally mediated clinical education", "Global Medical Education", 34, ("okafor", "santos"), ("equity", "digital learning", "clinical education"), ("sample-001", "sample-002")),
        ("sample-006", 2021, "Explainable machine learning for formative assessment feedback", "Digital Health Education", 43, ("chen", "demir", "johnson"), ("artificial intelligence", "assessment", "feedback"), ("sample-003", "sample-004")),
        ("sample-007", 2021, "International co-design of a virtual simulation curriculum", "Global Medical Education", 29, ("garcia", "okafor", "kim"), ("simulation", "curriculum", "co-design"), ("sample-001", "sample-004")),
        ("sample-008", 2022, "Student trust in AI-supported clinical decision exercises", "Medical Teacher Insights", 28, ("demir", "patel"), ("artificial intelligence", "trust", "clinical reasoning"), ("sample-003", "sample-005")),
        ("sample-009", 2023, "Generative AI as a reflective writing coach in residency", "Digital Health Education", 25, ("chen", "santos", "johnson"), ("generative AI", "feedback", "reflective practice"), ("sample-004", "sample-005", "sample-007")),
        ("sample-010", 2024, "Responsible use of large language models in medical assessment", "Medical Education Practice", 19, ("garcia", "demir", "patel"), ("generative AI", "assessment", "ethics"), ("sample-006", "sample-008")),
        ("sample-011", 2024, "A global competency framework for AI-ready medical graduates", "Global Medical Education", 16, ("okafor", "kim", "santos"), ("artificial intelligence", "curriculum", "competency framework"), ("sample-006", "sample-009")),
        ("sample-012", 2025, "Evaluating conversational tutors for diagnostic uncertainty", "Medical Teacher Insights", 8, ("chen", "kim", "johnson"), ("generative AI", "diagnostic reasoning", "virtual patients"), ("sample-009", "sample-010")),
    )

    return [
        RawRecord(
            source_id=source_id,
            source_database="sample",
            title=title,
            abstract=(
                "Synthetic demonstration record created for the bundled BibMedEd sample "
                "project. It is not a real publication and must not be cited."
            ),
            year=year,
            journal_name=journal,
            publication_type="Journal Article",
            authors=[_author(*authors[key]) for key in author_keys],
            mesh_terms=[],
            keywords=list(keywords),
            references=list(references),
            external_ids={},
        )
        for source_id, year, title, journal, _citations, author_keys, keywords, references
        in specifications
    ]


def _create_sample_project(db: Session) -> SearchProject:
    records = _sample_records()
    citation_counts = (64, 51, 39, 47, 34, 43, 29, 28, 25, 19, 16, 8)
    now = datetime.now(timezone.utc)
    project = SearchProject(
        id=SAMPLE_PROJECT_ID,
        name=SAMPLE_PROJECT_NAME,
        description=SAMPLE_PROJECT_DESCRIPTION,
        date_range_start=date(2018, 1, 1),
        date_range_end=date(2025, 12, 31),
    )

    try:
        db.add(project)
        db.flush()
        query = SearchQuery(
            project_id=project.id,
            query_string=SAMPLE_QUERY_STRING,
            database="sample",
            status=QueryStatus.completed,
            result_count=len(records),
            raw_result_count=len(records) + 1,
            duplicate_count=1,
            executed_at=now,
        )
        db.add(query)
        db.flush()

        persisted, _ = _persist_records(
            db,
            records,
            query.id,
            project.id,
            commit=False,
        )
        if persisted != len(records):
            raise RuntimeError(
                f"Sample project expected {len(records)} records but persisted {persisted}"
            )

        publications = {
            publication.pmid: publication
            for publication in db.query(Publication)
            .filter(Publication.project_id == project.id)
            .all()
        }
        for record, citation_count in zip(records, citation_counts, strict=True):
            publication = publications[record.source_id]
            publication.citation_count = citation_count
            publication.publication_type = record.publication_type

        excluded = publications["sample-005"]
        excluded.excluded = True
        excluded.exclusion_reason = "wrong_population"

        steps = (
            MethodologyStep(
                query_id=query.id,
                step_order=1,
                phase="search",
                source="BibMedEd sample dataset",
                action="Loaded the bundled synthetic demonstration dataset without external API calls",
                records_in=len(records) + 1,
                records_out=len(records) + 1,
                records_affected=0,
                parameters={"synthetic": True, "network_access": False},
                timestamp=now,
            ),
            MethodologyStep(
                query_id=query.id,
                step_order=2,
                phase="dedup",
                source="BibMedEd sample dataset",
                action="Removed one synthetic duplicate to demonstrate PRISMA accounting",
                records_in=len(records) + 1,
                records_out=len(records),
                records_affected=1,
                parameters={"matched_by": "source identifier", "synthetic": True},
                timestamp=now,
            ),
            MethodologyStep(
                query_id=query.id,
                step_order=3,
                phase="screening",
                source="BibMedEd sample dataset",
                action="Excluded one synthetic demonstration record with a PRISMA reason",
                records_in=len(records),
                records_out=len(records) - 1,
                records_affected=1,
                parameters={"reason": "wrong_population", "synthetic": True},
                timestamp=now,
            ),
        )
        db.add_all(steps)
        db.commit()
        db.refresh(project)
        return project
    except Exception:
        db.rollback()
        raise


def get_or_create_sample_project(db: Session) -> tuple[SearchProject, bool]:
    with _sample_creation_lock:
        existing = db.get(SearchProject, SAMPLE_PROJECT_ID)
        if existing is not None:
            return existing, False
        try:
            return _create_sample_project(db), True
        except IntegrityError:
            # A different process may have inserted the deterministic sample ID
            # after our lookup. Its transaction is complete once the uniqueness
            # failure is raised, so reload and reuse that project.
            db.rollback()
            existing = db.get(SearchProject, SAMPLE_PROJECT_ID)
            if existing is None:
                raise
            return existing, False
