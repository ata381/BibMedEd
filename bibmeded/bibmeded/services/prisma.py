"""PRISMA 2020 flow-diagram generation from the methodology log.

Produces an SVG that mirrors the PRISMA 2020 layout (Identification →
Removed before screening → Records screened → Reports sought for retrieval →
Reports assessed for eligibility → Included) using counts derived from the
project's `MethodologyStep` records and its per-stage exclusion summary.

Pure-Python: no extra dependencies. Returns the SVG as a string so the export
router can stream it directly with `media_type="image/svg+xml"`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Iterable, Mapping

from bibmeded.models.methodology import MethodologyStep
from bibmeded.models.publication import NOT_RETRIEVED_REASON, SCREENING_STAGES

TITLE_ABSTRACT = "title_abstract"
FULL_TEXT = "full_text"

# Keys are (screening_stage, exclusion_reason). A bare reason (or None) is the
# pre-stage summary shape and is read as a stage-less exclusion.
ExclusionSummary = Mapping[tuple[str | None, str | None] | str | None, int]


@dataclass(frozen=True)
class StagedExclusions:
    """Manual exclusions split into the PRISMA 2020 screening stages."""

    title_abstract_by_reason: dict[str, int]
    not_retrieved: int
    full_text_by_reason: dict[str, int]
    unrecorded_stage: int

    @property
    def title_abstract_total(self) -> int:
        return sum(self.title_abstract_by_reason.values())

    @property
    def full_text_total(self) -> int:
        return sum(self.full_text_by_reason.values())


def summarize_exclusions(summary: ExclusionSummary | None) -> StagedExclusions:
    """Group an exclusion summary by screening stage and reason.

    Exclusions without a recorded stage are counted at title/abstract, the same
    rule the 0004 migration applied to exclusions made before stages existed;
    ``unrecorded_stage`` keeps their number so reports can disclose it.
    """
    by_stage: dict[str, dict[str, int]] = {stage: {} for stage in SCREENING_STAGES}
    unrecorded = 0
    for key, n in (summary or {}).items():
        if n <= 0:
            continue
        stage, reason = key if isinstance(key, tuple) else (None, key)
        if stage is None:
            unrecorded += n
            stage = TITLE_ABSTRACT
        if stage not in by_stage:
            raise ValueError(f"Unknown screening stage {stage!r}; expected one of {SCREENING_STAGES}")
        reason_key = reason or "other"
        by_stage[stage][reason_key] = by_stage[stage].get(reason_key, 0) + n

    full_text = by_stage[FULL_TEXT]
    not_retrieved = full_text.pop(NOT_RETRIEVED_REASON, 0)
    return StagedExclusions(
        title_abstract_by_reason=by_stage[TITLE_ABSTRACT],
        not_retrieved=not_retrieved,
        full_text_by_reason=full_text,
        unrecorded_stage=unrecorded,
    )


def _step_stage(step: MethodologyStep) -> str:
    stage = (step.parameters or {}).get("screening_stage") or TITLE_ABSTRACT
    if stage not in SCREENING_STAGES:
        raise ValueError(
            f"Methodology step {step.step_order} has unknown screening stage {stage!r}; "
            f"expected one of {SCREENING_STAGES}"
        )
    return stage


_EXCLUSION_REASON_LABELS = {
    "wrong_study_design": "Wrong study design",
    "wrong_population": "Wrong population",
    "wrong_intervention": "Wrong intervention",
    "wrong_outcome": "Wrong outcome",
    "not_peer_reviewed": "Not peer-reviewed",
    "non_english": "Non-English",
    "duplicate": "Duplicate (manual)",
    "fulltext_unavailable": "Full-text unavailable",
    "other": "Other / unspecified",
}


@dataclass
class PrismaCounts:
    """Counts threaded through a PRISMA 2020 flow diagram.

    ``excluded_in_screening`` / ``excluded_by_reason`` are the title/abstract
    stage ("Records excluded"); the ``*_full_text`` fields and
    ``reports_not_retrieved`` are the full-text stage.
    """

    identified_by_source: dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    other_removed_before_screening: int = 0
    screened: int = 0
    excluded_in_screening: int = 0
    excluded_by_reason: dict[str, int] = field(default_factory=dict)
    reports_not_retrieved: int = 0
    excluded_full_text: int = 0
    excluded_full_text_by_reason: dict[str, int] = field(default_factory=dict)
    unrecorded_stage: int = 0
    included: int = 0

    @property
    def total_identified(self) -> int:
        return sum(self.identified_by_source.values())

    @property
    def reports_sought(self) -> int:
        return max(self.screened - self.excluded_in_screening, 0)

    @property
    def reports_assessed(self) -> int:
        return max(self.reports_sought - self.reports_not_retrieved, 0)


def compute_counts(
    steps: Iterable[MethodologyStep],
    exclusion_summary: ExclusionSummary | None = None,
    included_override: int | None = None,
) -> PrismaCounts:
    """Reduce a project's methodology steps to PRISMA flow-diagram counts.

    Phase → PRISMA box mapping:
      - ``search`` → "Records identified" (one entry per source).
      - ``dedup`` → "Duplicates removed before screening".
      - ``enrichment.records_affected`` → folded into "Other reasons removed
        before screening" (e.g., DOI resolution misses, iCite lookup failures).
        This is a pragmatic mapping rather than strict PRISMA 2020 — there is no
        dedicated PRISMA box for "enrichment failed", but a researcher cannot
        screen a record we couldn't enrich, so we treat the loss as
        pre-screening removal. Methodology log preserves the original phase
        label, so the exact cause is auditable.
      - ``fetch`` (``records_in - records_out``) → residual folded into "Other
        reasons removed before screening". The worker's fetch step covers ids
        that never became a persisted record (parse failures, per-record
        persist errors, etc.), but its ``records_out`` already excludes any
        records removed by that same run's cross-source ``dedup`` step (dedup
        happens inside the fetch loop, before persisting). To avoid
        double-subtracting those, we only fold in the residual —
        ``fetch loss - dedup records_affected`` for the same ``query_id`` —
        clamped at zero.
      - ``exclusion`` → "Records excluded" (title/abstract), or "Reports
        excluded" when ``parameters["screening_stage"] == "full_text"``.
      - ``exclusion_summary`` (live per-stage, per-reason counts of excluded
        publications) raises each stage's total to at least its row count.
        Full-text exclusions for ``fulltext_unavailable`` become "Reports not
        retrieved". Reports sought = records screened − records excluded;
        reports assessed = reports sought − reports not retrieved.
      - ``included_override``, when provided by the caller, overrides the
        post-screening count (it's the live ``excluded == False`` count and
        reflects manual exclusions that happened after the worker wrote its
        steps).
    """
    counts = PrismaCounts()
    steps = list(steps)

    # Per-query_id bookkeeping so a fetch-phase loss is only reconciled against
    # the dedup step that actually explains it (not an unrelated query's dedup).
    fetch_loss_by_query: dict[int, int] = {}
    dedup_affected_by_query: dict[int, int] = {}
    full_text_from_steps = 0

    for step in steps:
        if step.phase == "search":
            counts.identified_by_source[step.source] = (
                counts.identified_by_source.get(step.source, 0) + step.records_out
            )
        elif step.phase == "dedup":
            counts.duplicates_removed += step.records_affected
            dedup_affected_by_query[step.query_id] = (
                dedup_affected_by_query.get(step.query_id, 0) + step.records_affected
            )
        elif step.phase == "enrichment":
            counts.other_removed_before_screening += step.records_affected
        elif step.phase == "exclusion":
            if _step_stage(step) == FULL_TEXT:
                full_text_from_steps += step.records_affected
            else:
                counts.excluded_in_screening += step.records_affected
        elif step.phase == "fetch":
            loss = step.records_in - step.records_out
            if loss > 0:
                fetch_loss_by_query[step.query_id] = (
                    fetch_loss_by_query.get(step.query_id, 0) + loss
                )

    for query_id, loss in fetch_loss_by_query.items():
        already_explained_by_dedup = dedup_affected_by_query.get(query_id, 0)
        residual = loss - already_explained_by_dedup
        if residual > 0:
            counts.other_removed_before_screening += residual

    # Manual exclusions happen in the UI after the worker wrote its steps, so the
    # live row counts win whenever they exceed what the log recorded.
    staged = summarize_exclusions(exclusion_summary)
    counts.excluded_by_reason = staged.title_abstract_by_reason
    counts.excluded_in_screening = max(counts.excluded_in_screening, staged.title_abstract_total)
    counts.reports_not_retrieved = staged.not_retrieved
    counts.excluded_full_text_by_reason = staged.full_text_by_reason
    counts.excluded_full_text = max(full_text_from_steps - staged.not_retrieved, staged.full_text_total)
    counts.unrecorded_stage = staged.unrecorded_stage

    pre_screening = (
        counts.total_identified
        - counts.duplicates_removed
        - counts.other_removed_before_screening
    )
    counts.screened = max(pre_screening, 0)

    if included_override is not None:
        # Prefer the live count of non-excluded publications. Manual exclusions
        # via the UI happen AFTER the worker writes its methodology steps, so the
        # last step's records_out can be the pre-exclusion count.
        counts.included = max(included_override, 0)
    elif steps:
        last_with_out = next(
            (s for s in reversed(steps) if s.records_out is not None),
            None,
        )
        if last_with_out is not None:
            counts.included = max(last_with_out.records_out, 0)
        else:
            counts.included = max(counts.reports_assessed - counts.excluded_full_text, 0)
    else:
        counts.included = 0

    return counts


def render_svg(counts: PrismaCounts, project_name: str) -> str:
    """Render the PRISMA flow diagram as a standalone SVG string."""

    # Layout constants.
    width = 720
    box_w = 380
    box_h = 80
    right_box_w = 240
    # Main column sits left of centre so the side boxes fit inside the viewBox.
    col_x = 30
    right_col_x = col_x + box_w + 40
    gap = 36                              # vertical gap between boxes
    margin_top = 70                        # space for the title

    title_height = 40
    boxes = _layout(counts)
    total_height = margin_top + sum(b.height + gap for b in boxes) + 30

    parts: list[str] = []
    parts.append(
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {total_height}" '
        f'width="{width}" height="{total_height}" '
        f'font-family="Helvetica, Arial, sans-serif">'
    )

    parts.append(
        f'<text x="{width // 2}" y="30" text-anchor="middle" '
        f'font-size="18" font-weight="700" fill="#001e4f">'
        f"PRISMA 2020 flow diagram</text>"
    )
    parts.append(
        f'<text x="{width // 2}" y="52" text-anchor="middle" '
        f'font-size="12" fill="#43474e">{escape(project_name)}</text>'
    )

    # Render boxes + connecting arrows.
    y = margin_top + title_height // 2
    for i, box in enumerate(boxes):
        parts.append(_render_box(col_x, y, box_w, box.height, box.title, box.lines))

        if box.side_box is not None:
            side_y = y + (box.height - box.side_box.height) // 2
            parts.append(
                _render_box(
                    right_col_x,
                    side_y,
                    right_box_w,
                    box.side_box.height,
                    box.side_box.title,
                    box.side_box.lines,
                    stroke="#7d4f00",
                    title_fill="#7d4f00",
                )
            )
            # Horizontal arrow from main box to side box.
            parts.append(
                _render_arrow(
                    x1=col_x + box_w,
                    y1=side_y + box.side_box.height // 2,
                    x2=right_col_x,
                    y2=side_y + box.side_box.height // 2,
                )
            )

        if i < len(boxes) - 1:
            arrow_y1 = y + box.height
            arrow_y2 = y + box.height + gap
            parts.append(
                _render_arrow(
                    x1=col_x + box_w // 2,
                    y1=arrow_y1,
                    x2=col_x + box_w // 2,
                    y2=arrow_y2,
                )
            )

        y += box.height + gap

    parts.append("</svg>")
    return "".join(parts)


@dataclass
class _SideBox:
    title: str
    lines: list[str]
    height: int


@dataclass
class _MainBox:
    title: str
    lines: list[str]
    height: int
    side_box: _SideBox | None = None


def _layout(counts: PrismaCounts) -> list[_MainBox]:
    line_h = 18
    title_h = 24
    pad = 12

    def box_height(line_count: int) -> int:
        return title_h + max(line_count, 1) * line_h + pad

    identified_lines = [
        f"{src}: {n}" for src, n in counts.identified_by_source.items()
    ] or ["(no source-level counts available)"]
    identified = _MainBox(
        title=f"Records identified ({counts.total_identified})",
        lines=identified_lines,
        height=box_height(len(identified_lines) + 1),
    )

    removed_lines = []
    if counts.duplicates_removed:
        removed_lines.append(f"Duplicates removed: {counts.duplicates_removed}")
    if counts.other_removed_before_screening:
        removed_lines.append(
            f"Other reasons: {counts.other_removed_before_screening}"
        )
    if not removed_lines:
        removed_lines.append("None")
    removed = _MainBox(
        title=f"Records removed before screening ({counts.duplicates_removed + counts.other_removed_before_screening})",
        lines=removed_lines,
        height=box_height(len(removed_lines)),
    )

    def side_box(title: str, n: int, lines: list[str]) -> _SideBox | None:
        if not n:
            return None
        return _SideBox(title=f"{title} ({n})", lines=lines, height=box_height(len(lines)))

    def main_box(title: str, side: _SideBox | None = None) -> _MainBox:
        # Grow the main box to its side box so stacked side boxes never overlap.
        height = max(box_height(0), side.height if side else 0)
        return _MainBox(title=title, lines=[], height=height, side_box=side)

    title_abstract_lines = _reason_lines(counts.excluded_by_reason) or [
        "Below citation threshold or",
        "manual exclusion",
    ]
    if counts.unrecorded_stage:
        title_abstract_lines.append(f"incl. {counts.unrecorded_stage} without a recorded stage")
    full_text_lines = _reason_lines(counts.excluded_full_text_by_reason) or ["Reasons not recorded"]

    return [
        identified,
        removed,
        main_box(
            f"Records screened ({counts.screened})",
            side_box("Records excluded", counts.excluded_in_screening, title_abstract_lines),
        ),
        main_box(
            f"Reports sought for retrieval ({counts.reports_sought})",
            side_box("Reports not retrieved", counts.reports_not_retrieved, []),
        ),
        main_box(
            f"Reports assessed for eligibility ({counts.reports_assessed})",
            side_box("Reports excluded", counts.excluded_full_text, full_text_lines),
        ),
        main_box(f"Studies included in review ({counts.included})"),
    ]


def _reason_lines(by_reason: dict[str, int]) -> list[str]:
    return [
        f"{_EXCLUSION_REASON_LABELS.get(reason, reason)}: {n}"
        for reason, n in sorted(by_reason.items(), key=lambda kv: (-kv[1], kv[0]))
        if n
    ]


def _render_box(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    lines: list[str],
    stroke: str = "#001e4f",
    title_fill: str = "#001e4f",
) -> str:
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'rx="6" ry="6" fill="white" stroke="{stroke}" stroke-width="1.5"/>'
    ]
    parts.append(
        f'<text x="{x + w // 2}" y="{y + 20}" text-anchor="middle" '
        f'font-size="13" font-weight="700" fill="{title_fill}">'
        f"{escape(title)}</text>"
    )
    line_y = y + 42
    for line in lines:
        parts.append(
            f'<text x="{x + w // 2}" y="{line_y}" text-anchor="middle" '
            f'font-size="12" fill="#191c1e">{escape(line)}</text>'
        )
        line_y += 18
    return "".join(parts)


def _render_arrow(x1: int, y1: int, x2: int, y2: int) -> str:
    # Use a marker-less arrow built from a line + polygon for portability.
    head_size = 5
    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="#43474e" stroke-width="1.2"/>'
    ]
    # Arrowhead: vertical or horizontal, derived from the direction of travel.
    if x1 == x2 and y2 > y1:
        head = f"{x2 - head_size},{y2 - head_size} {x2 + head_size},{y2 - head_size} {x2},{y2}"
    elif y1 == y2 and x2 > x1:
        head = f"{x2 - head_size},{y2 - head_size} {x2 - head_size},{y2 + head_size} {x2},{y2}"
    else:
        head = ""
    if head:
        parts.append(f'<polygon points="{head}" fill="#43474e"/>')
    return "".join(parts)
