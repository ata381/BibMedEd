import pytest

from bibmeded.models import Publication, SearchProject, SearchQuery


@pytest.fixture
def sortable_publications(db):
    project = SearchProject(name="Sort query contract")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()
    publications = [
        Publication(
            pmid=f"sort-contract-{index}",
            title=title,
            year=year,
            citation_count=citations,
            query_id=query.id,
            project_id=project.id,
        )
        for index, (title, year, citations) in enumerate(
            [("Beta", 2024, 10), ("Gamma", 2022, 30), ("Alpha", 2023, 20)]
        )
    ]
    db.add_all(publications)
    db.commit()
    return project, publications


@pytest.mark.parametrize("sort_by", ["year", "title", "citation_count"])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_documented_sort_values(client, sortable_publications, sort_by, order):
    project, publications = sortable_publications
    response = client.get(
        f"/api/projects/{project.id}/publications",
        params={"sort_by": sort_by, "order": order},
    )
    assert response.status_code == 200
    expected = sorted(
        publications,
        key=lambda publication: (getattr(publication, sort_by), publication.id),
        reverse=order == "desc",
    )
    assert [item["id"] for item in response.json()["items"]] == [
        publication.id for publication in expected
    ]


@pytest.mark.parametrize(
    ("params", "descending"),
    [
        ({}, True),
        ({"sort_by": "unknown"}, True),
        ({"order": "unknown"}, False),
        ({"sort_by": "unknown", "order": "unknown"}, False),
        ({"sort_by": "", "order": ""}, False),
    ],
)
def test_sort_defaults_and_unknown_value_fallbacks(
    client, sortable_publications, params, descending
):
    project, publications = sortable_publications
    response = client.get(f"/api/projects/{project.id}/publications", params=params)
    assert response.status_code == 200
    expected = sorted(
        publications,
        key=lambda publication: (publication.year, publication.id),
        reverse=descending,
    )
    assert [item["id"] for item in response.json()["items"]] == [
        publication.id for publication in expected
    ]


def test_sort_query_openapi_metadata(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    operation = response.json()["paths"]["/api/projects/{project_id}/publications"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    for name, default, values in [
        ("sort_by", "year", ["year", "title", "citation_count"]),
        ("order", "desc", ["asc", "desc"]),
    ]:
        assert parameters[name]["in"] == "query"
        assert parameters[name]["required"] is False
        schema = parameters[name]["schema"]
        assert schema["type"] == "string"
        assert schema["default"] == default
        assert schema["enum"] == values
