"""PRISMA 2020 flow-diagram generation from the methodology log.

Produces an SVG that mirrors the four-tier PRISMA 2020 layout
(Identification → Removed before screening → Screening → Included) using
counts derived from the project's `MethodologyStep` records.

Pure-Python: no extra dependencies. Returns an `xml.etree.ElementTree`-built
SVG as a string so the export router can stream it directly with
`media_type="image/svg+xml"`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Iterable

from app.models.methodology import MethodologyStep


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
    """Counts threaded through a PRISMA 2020 flow diagram."""

    identified_by_source: dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    other_removed_before_screening: int = 0
    screened: int = 0
    excluded_in_screening: int = 0
    excluded_by_reason: dict[str, int] = field(default_factory=dict)
    included: int = 0

    @property
    def total_identified(self) -> int:
        return sum(self.identified_by_source.values())


def compute_counts(
    steps: Iterable[MethodologyStep],
    exclusion_summary: dict[str | None, int] | None = None,
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
      - ``exclusion`` → "Records excluded in screening".
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

    if exclusion_summary:
        # Surface PRISMA 2020 item 17 — per-reason breakdown of manual exclusions.
        cleaned: dict[str, int] = {}
        for reason, n in exclusion_summary.items():
            if not n:
                continue
            key = reason or "other"
            cleaned[key] = cleaned.get(key, 0) + n
        counts.excluded_by_reason = cleaned
        # If the methodology log didn't record an explicit `exclusion` step but rows in
        # the DB are flagged excluded, surface them in the diagram anyway.
        total_from_reasons = sum(cleaned.values())
        if total_from_reasons > counts.excluded_in_screening:
            counts.excluded_in_screening = total_from_reasons

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
            counts.included = counts.screened - counts.excluded_in_screening
    else:
        counts.included = 0

    return counts


def render_svg(counts: PrismaCounts, project_name: str) -> str:
    """Render the PRISMA flow diagram as a standalone SVG string."""

    # Layout constants.
    width = 720
    box_w = 380
    box_h = 80
    col_x = (width - box_w) // 2          # main column
    right_col_x = col_x + box_w + 60      # right-side "excluded" callouts
    right_box_w = 220
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

    side = None
    if counts.excluded_in_screening:
        if counts.excluded_by_reason:
            # PRISMA 2020 item 17 — show per-reason breakdown.
            reason_lines = [
                f"{_EXCLUSION_REASON_LABELS.get(r, r)}: {n}"
                for r, n in sorted(counts.excluded_by_reason.items(), key=lambda kv: -kv[1])
                if n
            ]
        else:
            reason_lines = ["Below citation threshold or", "manual exclusion"]
        side = _SideBox(
            title=f"Records excluded ({counts.excluded_in_screening})",
            lines=reason_lines,
            height=box_height(len(reason_lines)),
        )
    screened = _MainBox(
        title=f"Records screened ({counts.screened})",
        lines=[],
        height=box_height(0),
        side_box=side,
    )

    included = _MainBox(
        title=f"Studies included in review ({counts.included})",
        lines=[],
        height=box_height(0),
    )

    return [identified, removed, screened, included]


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
