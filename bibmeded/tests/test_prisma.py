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


def test_compute_counts_threads_exclusion_summary():
    """The PRISMA diagram should surface per-reason exclusion counts (PRISMA 2020 item 17)."""
    summary = {"non_english": 5, "not_peer_reviewed": 3, None: 0, "other": 1}
    counts = compute_counts([], exclusion_summary=summary)
    assert counts.excluded_by_reason == {"non_english": 5, "not_peer_reviewed": 3, "other": 1}
    # Falls back to sum when no explicit exclusion step exists.
    assert counts.excluded_in_screening == 9


def test_render_svg_shows_per_reason_breakdown_in_side_box():
    counts = PrismaCounts(
        identified_by_source={"pubmed": 100},
        screened=100,
        excluded_in_screening=8,
        excluded_by_reason={"non_english": 5, "not_peer_reviewed": 3},
        included=92,
    )
    svg = render_svg(counts, "P")
    assert "Non-English: 5" in svg
    assert "Not peer-reviewed: 3" in svg


def test_included_override_wins_over_methodology_log():
    """When the caller passes an actual non-excluded-publication count, it overrides
    the methodology log's last-step records_out. Manual exclusions via the UI happen
    after the worker writes its steps, so the override is the authoritative count."""
    steps = [
        _step(phase="search", source="pubmed", records_out=100),
        _step(phase="fetch", source="pubmed", records_in=100, records_out=100, step_order=2),
    ]
    counts = compute_counts(steps, included_override=42)
    assert counts.included == 42  # not 100 from the fetch step


def test_included_override_clamps_at_zero():
    counts = compute_counts([], included_override=-5)
    assert counts.included == 0


# ---------- fetch-phase losses (records lost between search and persist) ----------

def test_compute_counts_folds_pure_fetch_loss_into_other_removed_before_screening():
    """Records dropped during fetch (parse failures, per-record persist errors) with
    no accompanying cross-source dedup step must still be visible pre-screening."""
    steps = [
        _step(phase="search", source="pubmed", records_out=100),
        _step(phase="fetch", source="pubmed", records_in=100, records_out=90, step_order=2),
    ]
    counts = compute_counts(steps)
    assert counts.other_removed_before_screening == 10
    # 100 identified - 0 dedup - 10 fetch loss == 90 screened.
    assert counts.screened == 90


def test_compute_counts_fetch_loss_does_not_double_count_dedup_removed_records():
    """The fetch step's records_out already excludes cross-source-dedup-removed
    records (dedup happens inside the fetch loop, before persist). The fetch loss
    therefore contains both the cross-source-dedup count AND any other invisible
    loss. Only the residual (not already reflected in duplicates_removed) may be
    folded into other_removed_before_screening."""
    steps = [
        _step(phase="search", source="pubmed", records_out=100),
        # fetched 100 ids, persisted 70: lost 30 total (20 cross-source dupes + 10 other).
        _step(phase="fetch", source="pubmed", records_in=100, records_out=70, step_order=2),
        _step(
            phase="dedup", source="pubmed",
            records_in=90, records_out=70, records_affected=20, step_order=3,
        ),
    ]
    counts = compute_counts(steps)
    assert counts.duplicates_removed == 20
    assert counts.other_removed_before_screening == 10  # residual only, not 30
    assert counts.screened == 70  # matches the actual persisted count


def test_compute_counts_fetch_loss_fully_explained_by_dedup_adds_nothing_extra():
    """When the entire fetch-phase delta is accounted for by the dedup step's
    records_affected, no residual should be folded into other_removed_before_screening."""
    steps = [
        _step(phase="search", source="pubmed", records_out=100),
        _step(phase="fetch", source="pubmed", records_in=100, records_out=80, step_order=2),
        _step(
            phase="dedup", source="pubmed",
            records_in=100, records_out=80, records_affected=20, step_order=3,
        ),
    ]
    counts = compute_counts(steps)
    assert counts.duplicates_removed == 20
    assert counts.other_removed_before_screening == 0
    assert counts.screened == 80


def test_compute_counts_fetch_loss_correlates_per_query_not_globally():
    """A dedup step's records_affected for query B must not offset an unrelated
    fetch-phase loss for query A (and vice versa)."""
    steps = [
        # Query 1: pure fetch loss, no dedup step for this query.
        _step(query_id=1, phase="search", source="pubmed", records_out=50, step_order=1),
        _step(query_id=1, phase="fetch", source="pubmed", records_in=50, records_out=45, step_order=2),
        # Query 2: search + fetch (no loss) + dedup affecting query 2 only.
        _step(query_id=2, phase="search", source="openalex", records_out=100, step_order=1),
        _step(query_id=2, phase="fetch", source="openalex", records_in=100, records_out=80, step_order=2),
        _step(
            query_id=2, phase="dedup", source="openalex",
            records_in=100, records_out=80, records_affected=20, step_order=3,
        ),
    ]
    counts = compute_counts(steps)
    assert counts.duplicates_removed == 20
    # Query 1's 5-record fetch loss must surface fully (not absorbed by query 2's dedup).
    assert counts.other_removed_before_screening == 5
    assert counts.total_identified == 150
    assert counts.screened == 125  # 150 - 20 dedup - 5 fetch loss


def test_compute_counts_fetch_loss_ignores_non_positive_deltas():
    """records_out >= records_in (no loss, or a defensive/odd zero-delta step) must
    not produce a negative contribution."""
    steps = [
        _step(phase="search", source="pubmed", records_out=100),
        _step(phase="fetch", source="pubmed", records_in=100, records_out=100, step_order=2),
    ]
    counts = compute_counts(steps)
    assert counts.other_removed_before_screening == 0
    assert counts.screened == 100


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
