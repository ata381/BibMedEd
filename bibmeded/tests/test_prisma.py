"""Tests for the PRISMA flow-diagram service and export endpoint."""

from datetime import datetime, timezone

import pytest

from app.models.methodology import MethodologyStep
from app.services.prisma import PrismaCounts, compute_counts, render_svg


def _step(**kwargs):
    """Build a MethodologyStep with sensible defaults for tests."""
    defaults = dict(
        query_id=1,
        step_order=1,
        phase="search",
        source="pubmed",
        action="",
        records_in=0,
        records_out=0,
        records_affected=0,
        parameters={},
        timestamp=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return MethodologyStep(**defaults)


# ---------- compute_counts ----------

def test_compute_counts_empty_returns_zeros():
    counts = compute_counts([])
    assert counts.total_identified == 0
    assert counts.duplicates_removed == 0
    assert counts.screened == 0
    assert counts.excluded_in_screening == 0
    assert counts.included == 0


def test_compute_counts_sums_per_source_identifications():
    steps = [
        _step(phase="search", source="pubmed", records_out=1200),
        _step(phase="search", source="openalex", records_out=2400, step_order=2),
        _step(phase="search", source="crossref", records_out=600, step_order=3),
    ]
    counts = compute_counts(steps)
    assert counts.identified_by_source == {"pubmed": 1200, "openalex": 2400, "crossref": 600}
    assert counts.total_identified == 4200


def test_compute_counts_aggregates_multiple_search_steps_per_source():
    steps = [
        _step(phase="search", source="pubmed", records_out=500),
        _step(phase="search", source="pubmed", records_out=300, step_order=2),
    ]
    counts = compute_counts(steps)
    assert counts.identified_by_source == {"pubmed": 800}


def test_compute_counts_full_pipeline_screened_and_included():
    steps = [
        _step(phase="search", source="pubmed", records_out=1000),
        _step(phase="search", source="openalex", records_out=500, step_order=2),
        _step(phase="dedup", source="all", records_in=1500, records_out=1300, records_affected=200, step_order=3),
        _step(phase="exclusion", source="all", records_in=1300, records_out=900, records_affected=400, step_order=4),
    ]
    counts = compute_counts(steps)
    assert counts.total_identified == 1500
    assert counts.duplicates_removed == 200
    assert counts.screened == 1300
    assert counts.excluded_in_screening == 400
    # Last step's records_out (900) is the canonical "included" value.
    assert counts.included == 900


def test_compute_counts_treats_enrichment_drops_as_pre_screening_removal():
    steps = [
        _step(phase="search", source="pubmed", records_out=100),
        _step(phase="enrichment", source="icite", records_in=100, records_out=100, records_affected=15, step_order=2),
    ]
    counts = compute_counts(steps)
    assert counts.other_removed_before_screening == 15
    assert counts.screened == 85


def test_compute_counts_screened_clamps_at_zero():
    # Pathological: dedup removed more than were identified (shouldn't happen
    # in practice, but the renderer must never display negatives).
    steps = [
        _step(phase="search", source="pubmed", records_out=10),
        _step(phase="dedup", source="all", records_in=10, records_out=0, records_affected=50, step_order=2),
    ]
    counts = compute_counts(steps)
    assert counts.screened == 0


# ---------- render_svg ----------

def test_render_svg_returns_well_formed_svg():
    counts = PrismaCounts(
        identified_by_source={"pubmed": 100, "openalex": 50},
        duplicates_removed=20,
        screened=130,
        excluded_in_screening=10,
        included=120,
    )
    svg = render_svg(counts, project_name="Demo project")
    assert svg.startswith('<?xml version="1.0"')
    assert svg.rstrip().endswith("</svg>")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert "Demo project" in svg
    assert "PRISMA 2020" in svg


def test_render_svg_includes_all_counts_in_text():
    counts = PrismaCounts(
        identified_by_source={"pubmed": 1234},
        duplicates_removed=56,
        screened=1178,
        excluded_in_screening=78,
        included=1100,
    )
    svg = render_svg(counts, project_name="P")
    for needle in ("1234", "56", "1178", "78", "1100", "pubmed"):
        assert needle in svg, f"expected {needle!r} in rendered SVG"


def test_render_svg_escapes_project_name():
    svg = render_svg(PrismaCounts(), project_name="<script>alert(1)</script>")
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_render_svg_omits_side_box_when_no_exclusions():
    counts = PrismaCounts(
        identified_by_source={"pubmed": 100},
        duplicates_removed=0,
        screened=100,
        excluded_in_screening=0,
        included=100,
    )
    svg = render_svg(counts, "P")
    assert "Excluded" not in svg


# ---------- endpoint ----------

def test_export_prisma_endpoint_returns_svg(client, db):
    from app.models import SearchProject, SearchQuery

    project = SearchProject(name="PRISMA Test")
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="q", database="pubmed")
    db.add(query)
    db.flush()
    db.add_all(
        [
            _step(query_id=query.id, phase="search", source="pubmed", records_out=200),
            _step(query_id=query.id, phase="search", source="openalex", records_out=150, step_order=2),
            _step(query_id=query.id, phase="dedup", source="all", records_in=350, records_out=300, records_affected=50, step_order=3),
            _step(query_id=query.id, phase="exclusion", source="all", records_in=300, records_out=240, records_affected=60, step_order=4),
        ]
    )
    db.commit()

    resp = client.get(f"/api/projects/{project.id}/export/prisma")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "attachment" in resp.headers["content-disposition"].lower()
    body = resp.text
    assert body.startswith('<?xml')
    for needle in ("200", "150", "50", "60", "240", "pubmed", "openalex"):
        assert needle in body


def test_export_prisma_endpoint_404_for_unknown_project(client):
    resp = client.get("/api/projects/9999/export/prisma")
    assert resp.status_code == 404


def test_export_prisma_endpoint_handles_project_with_no_steps(client, db):
    from app.models import SearchProject

    project = SearchProject(name="Empty")
    db.add(project)
    db.commit()

    resp = client.get(f"/api/projects/{project.id}/export/prisma")
    assert resp.status_code == 200
    body = resp.text
    assert "PRISMA 2020" in body
    # When there are no steps, identification box shows the fallback line.
    assert "no source-level counts available" in body
