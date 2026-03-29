from datetime import datetime, timezone
from app.models.methodology import MethodologyStep


def test_create_methodology_step(db):
    from app.models import SearchProject, SearchQuery

    project = SearchProject(name="Test Project")
    db.add(project)
    db.flush()

    query = SearchQuery(project_id=project.id, query_string="test", database="pubmed")
    db.add(query)
    db.flush()

    step = MethodologyStep(
        query_id=query.id,
        step_order=1,
        phase="search",
        source="pubmed",
        action="PubMed E-Utilities search",
        records_in=0,
        records_out=847,
        records_affected=847,
        parameters={"query": "test", "date_range": "2019-2024"},
        timestamp=datetime.now(timezone.utc),
    )
    db.add(step)
    db.commit()

    saved = db.query(MethodologyStep).filter(MethodologyStep.query_id == query.id).first()
    assert saved is not None
    assert saved.phase == "search"
    assert saved.records_out == 847
    assert saved.parameters["query"] == "test"


def test_query_methodology_steps_relationship(db):
    from app.models import SearchProject, SearchQuery

    project = SearchProject(name="Test Project 2")
    db.add(project)
    db.flush()

    query = SearchQuery(project_id=project.id, query_string="test", database="pubmed")
    db.add(query)
    db.flush()

    step1 = MethodologyStep(
        query_id=query.id, step_order=1, phase="search", source="pubmed",
        action="Search", records_in=0, records_out=100, records_affected=100,
        parameters={}, timestamp=datetime.now(timezone.utc),
    )
    step2 = MethodologyStep(
        query_id=query.id, step_order=2, phase="fetch", source="pubmed",
        action="Fetch", records_in=100, records_out=98, records_affected=2,
        parameters={}, timestamp=datetime.now(timezone.utc),
    )
    db.add_all([step1, step2])
    db.commit()

    db.refresh(query)
    assert len(query.methodology_steps) == 2
    assert query.methodology_steps[0].step_order == 1


def test_export_methodology(client, db):
    from app.models import SearchProject, SearchQuery

    project = SearchProject(name="Export Test")
    db.add(project)
    db.flush()

    query = SearchQuery(project_id=project.id, query_string="AI AND medical education", database="pubmed")
    db.add(query)
    db.flush()

    steps = [
        MethodologyStep(
            query_id=query.id, step_order=1, phase="search", source="pubmed",
            action="PubMed E-Utilities search", records_in=0, records_out=847,
            records_affected=847,
            parameters={"query": "AI AND medical education", "database": "pubmed"},
            timestamp=datetime.now(timezone.utc),
        ),
        MethodologyStep(
            query_id=query.id, step_order=2, phase="fetch", source="pubmed",
            action="Batch fetch via PubMed E-Utilities", records_in=847, records_out=841,
            records_affected=6,
            parameters={"batch_size": 200},
            timestamp=datetime.now(timezone.utc),
        ),
    ]
    db.add_all(steps)
    db.commit()

    response = client.get(f"/api/projects/{project.id}/export/methodology")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    text = response.text
    assert "METHODOLOGY LOG" in text
    assert "Export Test" in text
    assert "PubMed E-Utilities search" in text
    assert "847" in text
    assert "841" in text
    assert "BibMedEd" in text


def test_export_methodology_no_steps(client, db):
    from app.models import SearchProject

    project = SearchProject(name="Empty Project")
    db.add(project)
    db.commit()

    response = client.get(f"/api/projects/{project.id}/export/methodology")
    assert response.status_code == 200
    text = response.text
    assert "No methodology steps recorded" in text
