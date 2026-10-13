"""Screening decision audit trail (issue #120).

Every change to a publication's screening state appends one ``ScreeningDecision``
row in the same transaction as the change; calls that change nothing append none.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bibmeded.models import MethodologyStep, Publication, ScreeningDecision, SearchProject, SearchQuery
from bibmeded.services import screening
from bibmeded.services.screening import INCLUDED, ScreeningState, apply_screening_state, load_decision_log

REVIEWER_HEADER = "X-Reviewer"


def _project_with_pubs(db, name, count=1, citation_count=None):
    project = SearchProject(name=name)
    db.add(project)
    db.flush()
    query = SearchQuery(project_id=project.id, query_string="t")
    db.add(query)
    db.flush()
    pubs = [
        Publication(pmid=f"{name}-{i}", title=f"P{i}", year=2024, citation_count=citation_count,
                    query_id=query.id, project_id=project.id)
        for i in range(count)
    ]
    db.add_all(pubs)
    db.commit()
    return project, pubs


def _decisions(db, project_id):
    return db.scalars(
        select(ScreeningDecision).where(ScreeningDecision.project_id == project_id).order_by(ScreeningDecision.id)
    ).all()


def _exclude_url(project, pub):
    return f"/api/projects/{project.id}/publications/{pub.id}/exclude"


def _bulk_url(project):
    return f"/api/projects/{project.id}/publications/bulk-exclude"


def _snapshot(decision):
    return (
        decision.previous_excluded, decision.previous_exclusion_reason, decision.previous_screening_stage,
        decision.excluded, decision.exclusion_reason, decision.screening_stage,
    )


def test_toggle_exclude_appends_one_decision_with_the_previous_state(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-exclude")
    before = datetime.now(timezone.utc).replace(tzinfo=None)

    r = client.patch(_exclude_url(project, pub), json={"reason": "wrong_outcome", "screening_stage": "full_text"})

    assert r.status_code == 200
    (decision,) = _decisions(db, project.id)
    assert decision.publication_id == pub.id
    assert _snapshot(decision) == (False, None, None, True, "wrong_outcome", "full_text")
    assert decision.source == "toggle"
    assert decision.run_id is None
    assert decision.criteria is None
    assert decision.reviewer is None
    # SQLite hands back naive datetimes; the column stores UTC either way.
    decided_at = decision.decided_at
    if decided_at.tzinfo is not None:
        decided_at = decided_at.astimezone(timezone.utc).replace(tzinfo=None)
    assert before <= decided_at <= datetime.now(timezone.utc).replace(tzinfo=None)


def test_toggle_re_include_appends_a_decision_that_reverses_the_exclusion(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-reinclude")
    client.patch(_exclude_url(project, pub), json={"reason": "non_english"})

    r = client.patch(_exclude_url(project, pub))

    assert r.json()["excluded"] is False
    exclusion, re_inclusion = _decisions(db, project.id)
    assert _snapshot(exclusion) == (False, None, None, True, "non_english", "title_abstract")
    assert _snapshot(re_inclusion) == (True, "non_english", "title_abstract", False, None, None)
    assert re_inclusion.id > exclusion.id


def test_toggle_records_the_reviewer_label_from_the_header(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-reviewer")

    client.patch(_exclude_url(project, pub), headers={REVIEWER_HEADER: "Reviewer A"})

    (decision,) = _decisions(db, project.id)
    assert decision.reviewer == "Reviewer A"


@pytest.mark.parametrize("label", ["", " leading-space", "=HYPERLINK()", "a" * 65, "tab\there", "semi;colon"])
def test_toggle_rejects_an_invalid_reviewer_label_without_changing_anything(client, db, label):
    project, (pub,) = _project_with_pubs(db, f"audit-bad-label-{len(label)}-{label[:3].strip()}")

    r = client.patch(_exclude_url(project, pub), headers={REVIEWER_HEADER: label})

    assert r.status_code == 422
    db.refresh(pub)
    assert pub.excluded is False
    assert _decisions(db, project.id) == []


def test_toggle_response_contract_is_unchanged_by_the_audit_trail(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-contract")
    r = client.patch(_exclude_url(project, pub), headers={REVIEWER_HEADER: "MB"})
    assert r.json() == {"id": pub.id, "excluded": True, "exclusion_reason": "other", "screening_stage": "title_abstract"}


def test_rejected_toggle_writes_no_decision(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-422")
    r = client.patch(
        _exclude_url(project, pub), json={"reason": "fulltext_unavailable", "screening_stage": "title_abstract"}
    )
    assert r.status_code == 422
    assert _decisions(db, project.id) == []


def test_bulk_exclude_appends_one_decision_per_affected_publication(client, db):
    project, pubs = _project_with_pubs(db, "audit-bulk", count=3, citation_count=0)
    _project_with_pubs(db, "audit-bulk-other", count=1, citation_count=0)
    cited = Publication(pmid="audit-bulk-cited", title="Cited", year=2024, citation_count=9,
                        query_id=pubs[0].query_id, project_id=project.id)
    db.add(cited)
    db.commit()

    r = client.post(
        _bulk_url(project),
        json={"citation_threshold": 0, "reason": "not_peer_reviewed"},
        headers={REVIEWER_HEADER: "MB"},
    )

    assert r.json()["excluded_count"] == 3
    decisions = _decisions(db, project.id)
    assert sorted(d.publication_id for d in decisions) == sorted(p.id for p in pubs)
    for decision in decisions:
        assert _snapshot(decision) == (False, None, None, True, "not_peer_reviewed", "title_abstract")
        assert decision.source == "bulk_exclude"
        assert decision.criteria == {"citation_threshold": 0}
        assert decision.reviewer == "MB"
    assert len({d.decided_at for d in decisions}) == 1
    (run_id,) = {d.run_id for d in decisions}
    assert uuid.UUID(run_id).version == 4


def test_bulk_exclude_that_matches_nothing_writes_no_decision(client, db):
    project, _ = _project_with_pubs(db, "audit-bulk-noop", count=2, citation_count=50)

    r = client.post(_bulk_url(project), json={"citation_threshold": 0})

    assert r.json()["excluded_count"] == 0
    assert _decisions(db, project.id) == []


def _bulk_steps(db, project):
    query_ids = [q.id for q in project.queries]
    return db.scalars(
        select(MethodologyStep)
        .where(MethodologyStep.query_id.in_(query_ids), MethodologyStep.phase == "bulk_exclude")
        .order_by(MethodologyStep.id)
    ).all()


def test_bulk_exclude_records_a_methodology_step_sharing_the_run_id(client, db):
    project, pubs = _project_with_pubs(db, "audit-bulk-step", count=2, citation_count=0)
    later_query = SearchQuery(project_id=project.id, query_string="second")
    db.add(later_query)
    db.flush()
    db.add(MethodologyStep(
        query_id=later_query.id, step_order=4, phase="search", source="pubmed", action="Search",
        records_in=0, records_out=0, records_affected=0, parameters={}, timestamp=datetime.now(timezone.utc),
    ))
    db.add(Publication(pmid="audit-bulk-step-cited", title="Cited", year=2024, citation_count=7,
                       query_id=later_query.id, project_id=project.id))
    db.commit()

    client.post(_bulk_url(project), json={"citation_threshold": 0, "reason": "non_english"},
                headers={REVIEWER_HEADER: "MB"})

    (step,) = _bulk_steps(db, project)
    (run_id,) = {d.run_id for d in _decisions(db, project.id)}
    assert (step.query_id, step.step_order) == (later_query.id, 5)
    assert (step.source, step.records_in, step.records_out, step.records_affected) == ("bulk_exclude", 3, 1, 2)
    assert step.parameters == {
        "run_id": run_id, "scope": "project", "citation_threshold": 0, "matched": 2, "excluded": 2,
        "skipped": 0, "reason": "non_english", "screening_stage": "title_abstract", "reviewer": "MB",
    }


def test_a_bulk_exclude_that_matches_nothing_still_appears_in_the_methodology_export(client, db):
    project, _ = _project_with_pubs(db, "audit-bulk-zero", count=1, citation_count=50)

    client.post(_bulk_url(project), json={"citation_threshold": 0})

    (step,) = _bulk_steps(db, project)
    assert step.parameters["matched"] == step.parameters["excluded"] == step.parameters["skipped"] == 0
    assert uuid.UUID(step.parameters["run_id"]).version == 4
    text = client.get(f"/api/projects/{project.id}/export/methodology").text
    section = text.split("SCREENING DECISION HISTORY (audit trail)\n", 1)[1].split("\n\n", 1)[0]
    assert "  Decisions logged: 0\n  Bulk exclusions:\n" in section
    assert f"(run {step.parameters['run_id']}): 0 matched, 0 excluded, 0 skipped;" in section


def test_each_bulk_request_gets_its_own_run_id(client, db):
    project, (first, second) = _project_with_pubs(db, "audit-bulk-runs", count=2, citation_count=0)
    second.citation_count = 3
    db.commit()

    client.post(_bulk_url(project), json={"citation_threshold": 0})
    client.post(_bulk_url(project), json={"citation_threshold": 5})

    first_run, second_run = (d.run_id for d in _decisions(db, project.id))
    assert first_run != second_run
    assert [s.parameters["run_id"] for s in _bulk_steps(db, project)] == [first_run, second_run]


def test_the_model_rejects_an_unknown_decision_source(db):
    project, (pub,) = _project_with_pubs(db, "audit-bad-source")
    db.add(ScreeningDecision(
        project_id=project.id, publication_id=pub.id, decided_at=datetime.now(timezone.utc), source="import",
        previous_excluded=False, excluded=True,
    ))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_decision_log_loads_only_identifiers_and_can_skip_publications(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-lean-load")
    client.patch(_exclude_url(project, pub))
    query_ids = [q.id for q in project.queries]

    db.expunge_all()
    (lean,) = load_decision_log(db, project.id, query_ids, with_publications=False).decisions
    assert "publication" in sa_inspect(lean).unloaded

    db.expunge_all()
    (full,) = load_decision_log(db, project.id, query_ids, with_publications=True).decisions
    assert "publication" not in sa_inspect(full).unloaded
    loaded_pub = full.publication
    assert loaded_pub.pmid == "audit-lean-load-0"
    assert {"title", "abstract"} <= sa_inspect(loaded_pub).unloaded


def test_bulk_exclude_skips_already_excluded_records(client, db):
    project, (first, second) = _project_with_pubs(db, "audit-bulk-skip", count=2, citation_count=0)
    client.patch(_exclude_url(project, first), json={"reason": "non_english"})

    r = client.post(_bulk_url(project), json={"citation_threshold": 0})

    assert r.json()["excluded_count"] == 1
    toggle, bulk = _decisions(db, project.id)
    assert toggle.publication_id == first.id
    assert bulk.publication_id == second.id


def test_bulk_exclude_writes_every_row_across_update_batches(client, db, monkeypatch):
    monkeypatch.setattr(screening, "UPDATE_BATCH_SIZE", 2)
    project, pubs = _project_with_pubs(db, "audit-bulk-batches", count=5, citation_count=0)

    r = client.post(_bulk_url(project), json={"citation_threshold": 0})

    assert r.json()["excluded_count"] == 5
    assert len(_decisions(db, project.id)) == 5
    for pub in pubs:
        db.refresh(pub)
        assert pub.excluded is True


def test_bulk_exclude_rejects_an_invalid_reviewer_label(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-bulk-bad-label", count=1, citation_count=0)
    r = client.post(_bulk_url(project), json={"citation_threshold": 0}, headers={REVIEWER_HEADER: "-1+1"})
    assert r.status_code == 422
    db.refresh(pub)
    assert pub.excluded is False
    assert _decisions(db, project.id) == []


def test_apply_screening_state_records_a_reason_change(db):
    project, (pub,) = _project_with_pubs(db, "audit-reason-change")
    apply_screening_state(db, pub, ScreeningState(True, "other", "title_abstract"), reviewer=None, source="toggle")

    decision = apply_screening_state(
        db, pub, ScreeningState(True, "wrong_population", "title_abstract"), reviewer="R2", source="toggle"
    )
    db.commit()

    assert decision is not None
    assert _snapshot(decision) == (True, "other", "title_abstract", True, "wrong_population", "title_abstract")
    assert (pub.excluded, pub.exclusion_reason, pub.screening_stage) == (True, "wrong_population", "title_abstract")
    assert len(_decisions(db, project.id)) == 2


def test_apply_screening_state_records_a_stage_change(db):
    _, (pub,) = _project_with_pubs(db, "audit-stage-change")
    apply_screening_state(db, pub, ScreeningState(True, "wrong_outcome", "title_abstract"), reviewer=None, source="toggle")

    decision = apply_screening_state(
        db, pub, ScreeningState(True, "wrong_outcome", "full_text"), reviewer=None, source="toggle"
    )
    db.commit()

    assert _snapshot(decision) == (True, "wrong_outcome", "title_abstract", True, "wrong_outcome", "full_text")
    assert pub.screening_stage == "full_text"


@pytest.mark.parametrize(
    "state",
    [INCLUDED, ScreeningState(True, "non_english", "title_abstract")],
    ids=["included-stays-included", "excluded-stays-identical"],
)
def test_apply_screening_state_writes_nothing_for_a_no_op(db, state):
    project, (pub,) = _project_with_pubs(db, f"audit-noop-{state.excluded}")
    if state.excluded:
        apply_screening_state(db, pub, state, reviewer=None, source="toggle")
        db.commit()
    before = len(_decisions(db, project.id))

    decision = apply_screening_state(db, pub, state, reviewer="R1", source="toggle")
    db.commit()

    assert decision is None
    assert len(_decisions(db, project.id)) == before


def test_apply_screening_state_keeps_unknown_legacy_values_verbatim(db):
    _, (pub,) = _project_with_pubs(db, "audit-legacy")
    pub.excluded = True
    pub.exclusion_reason = "legacy_reason"
    pub.screening_stage = None
    db.commit()

    decision = apply_screening_state(db, pub, INCLUDED, reviewer=None, source="toggle")
    db.commit()

    assert _snapshot(decision) == (True, "legacy_reason", None, False, None, None)


def test_methodology_export_reports_the_decision_history(client, db):
    project, (first, second, legacy) = _project_with_pubs(db, "audit-export", count=3)
    legacy.excluded = True
    legacy.exclusion_reason = "other"
    legacy.screening_stage = "title_abstract"
    db.commit()
    client.patch(_exclude_url(project, first), json={"reason": "non_english"}, headers={REVIEWER_HEADER: "MB"})
    client.patch(_exclude_url(project, first), headers={REVIEWER_HEADER: "Reviewer A"})
    client.patch(_exclude_url(project, second), json={"reason": "wrong_outcome", "screening_stage": "full_text"})

    text = client.get(f"/api/projects/{project.id}/export/methodology").text

    section = text.split("SCREENING DECISION HISTORY (audit trail)\n", 1)[1].split("\n\n", 1)[0]
    assert "  Decisions logged: 3\n    Exclusions: 2\n    Reversals (excluded record re-included): 1\n" in section
    assert "  Reviewer labels: MB, Reviewer A\n  Decisions without a reviewer label: 1\n" in section
    assert "1 currently excluded record has no logged decision." in section


def test_bundle_export_carries_the_decision_csv(client, db):
    import csv
    import io
    import zipfile

    project, (pub,) = _project_with_pubs(db, "audit-bundle")
    client.patch(_exclude_url(project, pub), headers={REVIEWER_HEADER: "MB"})

    bundle = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{project.id}/export/bundle").content))

    (name,) = [n for n in bundle.namelist() if "screening-decisions" in n]
    header, row = list(csv.reader(io.StringIO(bundle.read(name).decode("utf-8"))))
    record = dict(zip(header, row))
    assert record["reviewer"] == "MB"
    assert record["pmid"] == pub.pmid
    assert record["publication_id"] == str(pub.id)
    assert (record["action"], record["excluded"], record["exclusion_reason"]) == ("exclude", "true", "other")


def test_decisions_do_not_leak_into_another_project_export(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-scope-a")
    other, (other_pub,) = _project_with_pubs(db, "audit-scope-b")
    db.add(MethodologyStep(
        query_id=other_pub.query_id, step_order=1, phase="search", source="pubmed", action="Search",
        records_in=0, records_out=1, records_affected=1, parameters={}, timestamp=datetime.now(timezone.utc),
    ))
    db.commit()
    client.patch(_exclude_url(project, pub))

    text = client.get(f"/api/projects/{other.id}/export/methodology").text

    assert "  Decisions logged: 0" in text


def test_deleting_a_project_deletes_its_decisions(client, db):
    project, (pub,) = _project_with_pubs(db, "audit-delete")
    client.patch(_exclude_url(project, pub))
    project_id = project.id

    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 204

    db.expire_all()
    assert _decisions(db, project_id) == []
