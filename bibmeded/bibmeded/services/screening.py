"""Screening state changes and their append-only decision log (issue #120).

Every change to a publication's ``excluded`` / ``exclusion_reason`` /
``screening_stage`` goes through this module, which writes one
``ScreeningDecision`` per changed publication in the caller's transaction and
none when the requested state equals the current one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import batched

from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.orm import Session, joinedload

from bibmeded.models import Publication, ScreeningDecision

TOGGLE_SOURCE = "toggle"
BULK_EXCLUDE_SOURCE = "bulk_exclude"
SAMPLE_SEED_SOURCE = "sample_seed"

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
    most ``citation_threshold``, logging one decision per publication. Returns
    the number excluded. Does not commit."""
    rows = db.execute(
        select(Publication.id, Publication.exclusion_reason, Publication.screening_stage)
        .where(
            Publication.query_id.in_(query_ids),
            Publication.excluded == False,
            (Publication.citation_count == None) | (Publication.citation_count <= citation_threshold),
        )
        .order_by(Publication.id)
        # Holds the matched rows on Postgres so a concurrent toggle cannot change
        # them between this snapshot and the update; SQLite ignores it.
        .with_for_update()
    ).all()
    if not rows:
        return 0
    decided_at = _now_utc()
    criteria = {"citation_threshold": citation_threshold}
    for batch in batched([row.id for row in rows], UPDATE_BATCH_SIZE):
        db.execute(
            update(Publication)
            .where(Publication.id.in_(batch))
            .values(
                excluded=target.excluded,
                exclusion_reason=target.exclusion_reason,
                screening_stage=target.screening_stage,
            )
            .execution_options(synchronize_session="fetch")
        )
    db.execute(
        insert(ScreeningDecision),
        [
            {
                "project_id": project_id,
                "publication_id": row.id,
                "decided_at": decided_at,
                "reviewer": reviewer,
                "source": BULK_EXCLUDE_SOURCE,
                "criteria": criteria,
                **_decision_values(ScreeningState(False, row.exclusion_reason, row.screening_stage), target),
            }
            for row in rows
        ],
    )
    return len(rows)


def load_decision_log(db: Session, project_id: int, query_ids: list[int]) -> ScreeningDecisionLog:
    decisions = db.scalars(
        select(ScreeningDecision)
        .options(joinedload(ScreeningDecision.publication))
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
