import io
import re
import zipfile
from datetime import datetime, timezone

from bibmeded.models import MethodologyStep, SearchProject, SearchQuery
from bibmeded.services.demo_seed import seed_demo_data


def test_sample_reporting_exports_match_project_evidence(client, db):
    project = seed_demo_data(db)
    export = f"/api/projects/{project.id}/export"
    checklist = client.get(f"{export}/checklist")
    appendix = client.get(f"{export}/checklist?guideline=prisma-s")
    methodology = client.get(f"{export}/methodology")
    assert checklist.status_code == appendix.status_code == methodology.status_code == 200
    assert checklist.headers["content-type"].startswith("text/markdown")
    assert "attachment" in checklist.headers["content-disposition"]
    assert re.findall(r"^\| (\d+) \|", checklist.text, re.MULTILINE) == [
        str(number) for number in range(1, 21)
    ]
    assert "synthetic demonstration search" in checklist.text
    assert "title&#95;abstract / wrong&#95;population: 1" in checklist.text
    assert "Included records: 11" in checklist.text
    assert "Studies included: 11" in methodology.text
    assert "Synthetic input records: 13. No upstream search was run." in appendix.text
    assert "source identifier, 1 removed" in appendix.text

    bundle = client.get(f"{export}/bundle")
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        manifest = archive.read("MANIFEST.txt").decode()
        for response, suffix in ((checklist, ".md"), (appendix, ".txt")):
            filename = response.headers["content-disposition"].split('"')[1]
            assert filename.endswith(suffix) and filename in manifest
            assert archive.read(filename) == response.content


def test_live_count_fields_and_query_are_distinct_and_literal(client, db):
    project = SearchProject(name="Fixture")
    db.add(project)
    db.flush()
    text = '  "alpha" | [beta]\nAND <gamma>  '
    query = SearchQuery(project_id=project.id, query_string=text, database="openalex")
    db.add(query)
    db.flush()
    db.add(MethodologyStep(
        query_id=query.id, step_order=1, phase="search", source="openalex",
        action="OpenAlex API search", records_in=0, records_out=47, records_affected=47,
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        parameters={
            "query": text, "searched_at": "2026-01-02T09:30:00+00:00",
            "year_filters": {"year_end": "2025"},
            "upstream_total": 47, "retrieved_ids": 20, "max_results": 20, "capped": True,
        },
    ))
    db.commit()

    path = f"/api/projects/{project.id}/export/checklist"
    appendix = client.get(f"{path}?guideline=prisma-s")
    assert appendix.status_code == 200
    assert text in appendix.text
    assert "Search date: 2026-01-02T09:30:00+00:00" in appendix.text
    assert "Separate publication-year filters: end year: 2025" in appendix.text
    assert "Upstream matches: 47" in appendix.text
    assert "Retrieved identifiers: 20" in appendix.text
    assert "Configured retrieval cap: 20" in appendix.text
    assert "Retrieval truncated: yes" in appendix.text
    checklist = client.get(path)
    assert checklist.status_code == 200
    assert "&#124; &#91;beta&#93; AND &#60;gamma&#62;" in checklist.text
    assert "| 9 | State the criteria for including and excluding records. | not recorded | |" in checklist.text


def test_reports_handle_empty_projects_and_validate_guideline(client, db):
    project = SearchProject(name="Empty")
    db.add(project)
    db.commit()
    path = f"/api/projects/{project.id}/export/checklist"
    assert "| 6 | Identify all sources consulted. | not recorded | |" in client.get(path).text
    assert "Searches: not recorded" in client.get(f"{path}?guideline=prisma-s").text
    assert client.get(f"{path}?guideline=unknown").status_code == 422
    assert client.get("/api/projects/999999/export/checklist").status_code == 404
