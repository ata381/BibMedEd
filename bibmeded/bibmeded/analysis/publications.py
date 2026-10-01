import math
from collections import Counter
from datetime import date

from sqlalchemy.orm import Session
from bibmeded.models import Publication, SearchProject


_EMPTY = {
    "yearly_counts": [],
    "total": 0,
    "growth_rates": [],
    "cumulative": [],
    "field_maturity": None,
}

_INSUFFICIENT_YEARS_REASON = "At least two full calendar years of data are required to compute CAGR."
_ZERO_START_REASON = "CAGR is undefined because the first full calendar year has zero publications."
_NON_POSITIVE_GROWTH_REASON = "Doubling time is not defined for non-positive growth (CAGR <= 0)."


def _growth_summary(yearly_items: list[tuple[int, int]], current_year: int) -> dict:
    """Compound annual growth rate and doubling time over full calendar years.

    ``yearly_items`` is the zero-filled ``(year, count)`` series. Years from
    ``current_year`` onward are incomplete and excluded, so a partial current
    year cannot drag the end point down. ``cagr`` is a percentage; periods are
    ``end_year - start_year``.
    """
    full_years = [(year, count) for year, count in yearly_items if year < current_year]
    summary = {
        "cagr": None,
        "doubling_time_years": None,
        "start_year": full_years[0][0] if full_years else None,
        "end_year": full_years[-1][0] if full_years else None,
        "excluded_current_year": any(year == current_year and count > 0 for year, count in yearly_items),
        "reason": None,
    }
    if len(full_years) < 2:
        summary["reason"] = _INSUFFICIENT_YEARS_REASON
        return summary

    (start_year, start_count), (end_year, end_count) = full_years[0], full_years[-1]
    if start_count == 0:
        summary["reason"] = _ZERO_START_REASON
        return summary

    rate = (end_count / start_count) ** (1 / (end_year - start_year)) - 1
    summary["cagr"] = round(rate * 100, 2)
    if rate <= 0:
        summary["reason"] = _NON_POSITIVE_GROWTH_REASON
    else:
        summary["doubling_time_years"] = round(math.log(2) / math.log(1 + rate), 2)
    return summary


def _empty_result(current_year: int) -> dict:
    return {**_EMPTY, "growth_summary": _growth_summary([], current_year)}


def _classify_maturity(cumulative: list[dict]) -> dict | None:
    """Classify field lifecycle by fitting a logistic curve to cumulative counts.

    Returns ``None`` if there are fewer than 4 data points or scipy is unavailable.
    Otherwise returns::

        {
          "phase": "emerging" | "growing" | "mature" | "saturating" | "undetermined",
          "carrying_capacity": float,   # estimated asymptote K
          "midpoint_year": float,       # year at which the curve crosses K/2
          "growth_rate": float,         # logistic growth rate r
          "fit_quality": float,         # R^2 of the fit, range [0, 1]
          "progress": float,            # current_cumulative / K, range [0, 1]
          "method": "logistic-growth (Bettencourt & Kaur 2011)",
        }

    ``phase`` is forced to ``"undetermined"`` when ``fit_quality < 0.85`` — common
    for corpora with a plateau-and-resurgence shape, where the single-growth-phase
    logistic model does not apply cleanly.
    """
    if len(cumulative) < 4:
        return None
    try:
        import numpy as np
        from scipy.optimize import curve_fit
    except ImportError:
        return None

    years = np.array([d["year"] for d in cumulative], dtype=float)
    totals = np.array([d["cumulative"] for d in cumulative], dtype=float)
    if totals[-1] == 0:
        return None

    def logistic(t, K, r, t0):
        return K / (1.0 + np.exp(-r * (t - t0)))

    K0 = float(totals[-1]) * 1.5
    r0 = 0.5
    t0_0 = float(years[len(years) // 2])
    try:
        popt, _ = curve_fit(
            logistic, years, totals, p0=[K0, r0, t0_0],
            maxfev=2000, bounds=([totals[-1], 0.01, years[0] - 5], [K0 * 10, 5.0, years[-1] + 5]),
        )
    except (RuntimeError, ValueError):
        return None
    K, r, t0 = (float(x) for x in popt)
    predicted = logistic(years, K, r, t0)
    ss_res = float(np.sum((totals - predicted) ** 2))
    ss_tot = float(np.sum((totals - totals.mean()) ** 2))
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    progress = totals[-1] / K if K > 0 else 0.0
    if progress < 0.25:
        phase = "emerging"
    elif progress < 0.6:
        phase = "growing"
    elif progress < 0.85:
        phase = "mature"
    else:
        phase = "saturating"

    # Don't report a confident phase label when the logistic fit is poor — common for
    # corpora with a plateau-and-resurgence shape (e.g. AI-in-medical-education post-2022).
    # Threshold of 0.85 matches the conservative bar most bibliometric reviewers expect.
    if r_squared < 0.85:
        phase = "undetermined"

    return {
        "phase": phase,
        "carrying_capacity": round(K, 1),
        "midpoint_year": round(t0, 1),
        "growth_rate": round(r, 3),
        "fit_quality": round(r_squared, 3),
        "progress": round(progress, 3),
        "method": "logistic-growth (Bettencourt & Kaur 2011)",
    }


def analyze_publication_trends(db: Session, project_id: int) -> dict:
    current_year = date.today().year
    project = db.get(SearchProject, project_id)
    if not project:
        return _empty_result(current_year)
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return _empty_result(current_year)
    pubs = db.query(Publication.year).filter(
        Publication.query_id.in_(query_ids), Publication.year.isnot(None), Publication.excluded == False).all()
    if not pubs:
        return _empty_result(current_year)

    yearly_counter = Counter(int(year) for (year,) in pubs if year is not None)
    # Zero-fill years with no publications so every entry in `yearly_items` is
    # calendar-adjacent to the next. Without this, a corpus with a gap year
    # (e.g. 3 pubs in 2015, none in 2016-2018, 9 in 2019) would silently
    # compress that 4-year gap into a single "growth_rates" entry -- reporting
    # a fabricated "200% YoY" surge for 2019 instead of the true multi-year
    # change. Zero-filling is also the most honest representation of
    # `yearly_counts` itself: the zero-output years are real data, not absent.
    min_year, max_year = min(yearly_counter), max(yearly_counter)
    yearly_items = [(year, yearly_counter.get(year, 0)) for year in range(min_year, max_year + 1)]
    yearly_counts = [{"year": year, "count": count} for year, count in yearly_items]
    counts = [count for _, count in yearly_items]

    growth_rates = []
    for i in range(1, len(counts)):
        prev = counts[i - 1]
        curr = counts[i]
        if prev > 0:
            rate = round((curr - prev) / prev * 100, 1)
        elif curr == 0:
            rate = 0.0
        else:
            # Growth from a zero-publication year is mathematically undefined
            # (division by zero) -- report `None` rather than a misleading 0%
            # or an inflated/fabricated percentage.
            rate = None
        growth_rates.append({"year": yearly_items[i][0], "rate": rate})

    cumulative = []
    total = 0
    for year, count in yearly_items:
        total += count
        cumulative.append({"year": year, "cumulative": total})

    field_maturity = _classify_maturity(cumulative)

    return {
        "yearly_counts": yearly_counts,
        "total": len(pubs),
        "growth_rates": growth_rates,
        "cumulative": cumulative,
        "field_maturity": field_maturity,
        "growth_summary": _growth_summary(yearly_items, current_year),
    }
