"""Screening state changes and their append-only decision log (issue #120).

Every change to a publication's ``excluded`` / ``exclusion_reason`` /
``screening_stage`` goes through this module, which writes one
``ScreeningDecision`` per changed publication in the caller's transaction and
none when the requested state equals the current one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import batched

from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.orm import Session, joinedload, load_only, raiseload

from bibmeded.models import MethodologyStep, Publication, ScreeningDecision

TOGGLE_SOURCE = "toggle"
BULK_EXCLUDE_SOURCE = "bulk_exclude"
SAMPLE_SEED_SOURCE = "sample_seed"
BULK_EXCLUDE_PHASE = "bulk_exclude"

# Keeps each UPDATE's IN list below SQLite's historical 999 bound-parameter limit.
UPDATE_BATCH_SIZE = 500


@dataclass(frozen=True)
class ScreeningState:
    excluded: bool
    exclusion_reason: str | None
    screening_stage: str | None


INCLUDED = ScreeningState(excluded=False, exclusion_reason=None, screening_stage=None)


@dataclass(frozen=True)
class ScreeningDecisionLog:
    """A project's decisions in log order, plus how many of its current
    exclusions have no logged decision (made before the log existed)."""

    decisions: tuple[ScreeningDecision, ...]
    unlogged_exclusions: int = 0


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def current_state(pub: Publication) -> ScreeningState:
    return ScreeningState(bool(pub.excluded), pub.exclusion_reason, pub.screening_stage)


def _decision_values(previous: ScreeningState, target: ScreeningState) -> dict:
    return {
        "previous_excluded": previous.excluded,
        "previous_exclusion_reason": previous.exclusion_reason,
        "previous_screening_stage": previous.screening_stage,
        "excluded": target.excluded,
        "exclusion_reason": target.exclusion_reason,
        "screening_stage": target.screening_stage,
    }


def apply_screening_state(
    db: Session,
    pub: Publication,
    target: ScreeningState,
    *,
    reviewer: str | None,
    source: str,
) -> ScreeningDecision | None:
    """Move ``pub`` to ``target`` and log the change; return None for a no-op.

    Does not commit, so the state change and its decision land together.
    """
    previous = current_state(pub)
    if previous == target:
        return None
    decision = ScreeningDecision(
        project_id=pub.project_id,
        publication_id=pub.id,
        decided_at=_now_utc(),
        reviewer=reviewer,
        source=source,
        criteria=None,
        **_decision_values(previous, target),
    )
    pub.excluded = target.excluded
    pub.exclusion_reason = target.exclusion_reason
    pub.screening_stage = target.screening_stage
    db.add(decision)
    return decision


def exclude_by_citation_threshold(
    db: Session,
    *,
    project_id: int,
    query_ids: list[int],
    citation_threshold: int,
    target: ScreeningState,
    reviewer: str | None,
) -> int:
    """Exclude every included publication whose citation count is missing or at
    most ``citation_threshold``. Logs one decision per excluded publication and
    one ``bulk_exclude`` methodology step for the request, even when nothing
    matched, all sharing a fresh ``run_id``. Returns the number excluded. Does
    not commit."""
    included_before = db.scalar(
        select(func.count(Publication.id)).where(Publication.query_id.in_(query_ids), Publication.excluded == False)
    )
    rows = db.execute(
        select(Publication.id, Publication.exclusion_reason, Publication.screening_stage)
        .where(
            Publication.query_id.in_(query_ids),
            Publication.excluded == False,
            Publication.citation_count.is_(None) | (Publication.citation_count <= citation_threshold),
        )
        .order_by(Publication.id)
        # FOR NO KEY UPDATE on Postgres: only non-key columns change, and plain
        # FOR UPDATE blocks (and can deadlock with) the worker's KEY SHARE locks
        # from inserting author and keyword links during a fetch. SQLite ignores it.
        .with_for_update(key_share=True)
    ).all()
    run_id = str(uuid.uuid4())
    decided_at = _now_utc()
    # The UPDATE re-checks ``excluded`` so that on SQLite, where the row lock is
    # a no-op, a concurrent request that already excluded a selected row is not
    # overwritten and gets no second decision; those rows count as skipped.
    updated_ids: set[int] = set()
    for batch in batched([row.id for row in rows], UPDATE_BATCH_SIZE):
        updated_ids.update(
            db.scalars(
                update(Publication)
                .where(Publication.id.in_(batch), Publication.excluded.is_(False))
                .values(
                    excluded=target.excluded,
                    exclusion_reason=target.exclusion_reason,
                    screening_stage=target.screening_stage,
                )
                .returning(Publication.id)
                .execution_options(synchronize_session="fetch")
            )
        )
    excluded_rows = [row for row in rows if row.id in updated_ids]
    if excluded_rows:
        db.execute(
            insert(ScreeningDecision),
            [
                {
                    "project_id": project_id,
                    "publication_id": row.id,
                    "decided_at": decided_at,
                    "reviewer": reviewer,
                    "source": BULK_EXCLUDE_SOURCE,
                    "run_id": run_id,
                    "criteria": {"citation_threshold": citation_threshold},
                    **_decision_values(ScreeningState(False, row.exclusion_reason, row.screening_stage), target),
                }
                for row in excluded_rows
            ],
        )
    db.add(_bulk_exclude_step(
        db,
        query_id=max(query_ids),
        run_id=run_id,
        decided_at=decided_at,
        citation_threshold=citation_threshold,
        counts={
            "matched": len(rows),
            "excluded": len(excluded_rows),
            "skipped": len(rows) - len(excluded_rows),
        },
        included_before=included_before,
        target=target,
        reviewer=reviewer,
    ))
    return len(excluded_rows)


def _bulk_exclude_step(
    db: Session,
    *,
    query_id: int,
    run_id: str,
    decided_at: datetime,
    citation_threshold: int,
    counts: dict[str, int],
    included_before: int,
    target: ScreeningState,
    reviewer: str | None,
) -> MethodologyStep:
    # Steps belong to a query but a bulk exclusion covers the whole project, so
    # it is filed under the project's latest query with scope "project", and the
    # exports keep it out of the per-query pipeline and PRISMA totals.
    # Same MAX + 1 rule as the worker's _next_step_order; importing it would pull
    # Celery and the adapters into the request path.
    last_step = db.scalar(select(func.max(MethodologyStep.step_order)).where(MethodologyStep.query_id == query_id))
    return MethodologyStep(
        query_id=query_id,
        step_order=(last_step or 0) + 1,
        phase=BULK_EXCLUDE_PHASE,
        source=BULK_EXCLUDE_SOURCE,
        action=f"Bulk exclusion of included records with citation count missing or at most {citation_threshold}",
        records_in=included_before,
        records_out=included_before - counts["excluded"],
        records_affected=counts["excluded"],
        parameters={
            "run_id": run_id,
            "scope": "project",
            "citation_threshold": citation_threshold,
            **counts,
            "reason": target.exclusion_reason,
            "screening_stage": target.screening_stage,
            "reviewer": reviewer,
        },
        timestamp=decided_at,
    )


def load_decision_log(
    db: Session,
    project_id: int,
    query_ids: list[int],
    *,
    with_publications: bool = True,
) -> ScreeningDecisionLog:
    """``with_publications`` loads each decision's PMID and DOI for the CSV. The
    text summary never reads them, so it skips the join, and raiseload turns any
    accidental per-row lazy load into an error instead of an N+1."""
    publication_option = (
        joinedload(ScreeningDecision.publication).options(load_only(Publication.pmid, Publication.doi))
        if with_publications
        else raiseload(ScreeningDecision.publication)
    )
    decisions = db.scalars(
        select(ScreeningDecision)
        .options(publication_option)
        .where(ScreeningDecision.project_id == project_id)
        .order_by(ScreeningDecision.id)
    ).all()
    unlogged = 0
    if query_ids:
        unlogged = db.scalar(
            select(func.count(Publication.id)).where(
                Publication.query_id.in_(query_ids),
                Publication.excluded == True,
                ~exists().where(ScreeningDecision.publication_id == Publication.id),
            )
        )
    return ScreeningDecisionLog(decisions=tuple(decisions), unlogged_exclusions=unlogged)
