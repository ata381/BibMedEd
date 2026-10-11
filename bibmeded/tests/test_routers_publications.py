from bibmeded.models import Author, Journal, Publication, SearchProject, SearchQuery

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
    pub = Publication(pmid="11111111", title="Test Paper", year=2024, journal_id=journal.id, query_id=query.id, project_id=project.id)
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
        pub = Publication(pmid=f"sort{i}", title=f"Paper {i}", year=year, query_id=query.id, project_id=project.id)
        db.add(pub)
    db.commit()
    response = client.get(f"/api/projects/{project.id}/publications?sort_by=year&order=asc")
    years = [p["year"] for p in response.json()["items"]]
    assert years == sorted(years)


def test_toggle_exclude_with_reason(client, db):
    project = SearchProject(name="Exclude")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    pub = Publication(pmid="ex1", title="P", year=2024, query_id=query.id, project_id=project.id)
    db.add(pub)
    db.commit()

    # Exclude with a reason.
    r = client.patch(f"/api/projects/{project.id}/publications/{pub.id}/exclude", json={"reason": "non_english"})
    assert r.status_code == 200
    body = r.json()
    assert body["excluded"] is True
    assert body["exclusion_reason"] == "non_english"

    # Toggle back (re-include) clears the reason.
    r2 = client.patch(f"/api/projects/{project.id}/publications/{pub.id}/exclude", json={})
    assert r2.json()["excluded"] is False
    assert r2.json()["exclusion_reason"] is None


def test_toggle_exclude_rejects_unknown_reason(client, db):
    project = SearchProject(name="BadReason")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    pub = Publication(pmid="badr", title="P", year=2024, query_id=query.id, project_id=project.id)
    db.add(pub)
    db.commit()
    r = client.patch(
        f"/api/projects/{project.id}/publications/{pub.id}/exclude",
        json={"reason": "made_up_reason"},
    )
    assert r.status_code == 422  # Pydantic rejects unknown Literal


def test_bulk_exclude_stamps_reason(client, db):
    project = SearchProject(name="Bulk")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    db.add_all([
        Publication(pmid=f"b{i}", title=f"P{i}", year=2024, citation_count=0, query_id=query.id, project_id=project.id)
        for i in range(3)
    ])
    db.commit()

    r = client.post(
        f"/api/projects/{project.id}/publications/bulk-exclude",
        json={"citation_threshold": 0, "reason": "not_peer_reviewed"},
    )
    assert r.status_code == 200
    assert r.json()["excluded_count"] == 3
    assert r.json()["reason"] == "not_peer_reviewed"
    # Verify the reason landed on the rows.
    listed = client.get(f"/api/projects/{project.id}/publications").json()
    for item in listed["items"]:
        assert item["excluded"] is True
        assert item["exclusion_reason"] == "not_peer_reviewed"


def test_list_publications_pagination_deterministic_with_tied_sort_keys(client, db):
    project = SearchProject(name="Pagination Tie Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="test")
    db.add(query)
    db.flush()

    # 25 publications with identical sort values: same year, same title, citation_count=0
    pubs = [
        Publication(
            pmid=f"tie{i}",
            title="Identical Title",
            year=2024,
            citation_count=0,
            query_id=query.id,
            project_id=project.id,
        )
        for i in range(25)
    ]
    db.add_all(pubs)
    db.commit()

    expected_ids = {p.id for p in pubs}
    assert len(expected_ids) == 25

    page_size = 7
    for sort_by in ["year", "title", "citation_count"]:
        for order in ["asc", "desc"]:
            collected_ids = []
            offset = 0
            while True:
                response = client.get(
                    f"/api/projects/{project.id}/publications?sort_by={sort_by}&order={order}&limit={page_size}&offset={offset}"
                )
                assert response.status_code == 200
                data = response.json()
                items = data["items"]
                if not items:
                    break
                collected_ids.extend([item["id"] for item in items])
                offset += len(items)
                if len(items) < page_size:
                    break

            assert len(collected_ids) == 25
            assert set(collected_ids) == expected_ids
            assert len(set(collected_ids)) == len(collected_ids)
            if order == "asc":
                assert collected_ids == sorted(collected_ids)
            else:
                assert collected_ids == sorted(collected_ids, reverse=True)

