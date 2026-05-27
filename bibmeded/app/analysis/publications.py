from collections import Counter
from sqlalchemy.orm import Session
from app.models import Publication, SearchProject


_EMPTY = {
    "yearly_counts": [],
    "total": 0,
    "growth_rates": [],
    "cumulative": [],
    "field_maturity": None,
}


def _classify_maturity(cumulative: list[dict]) -> dict | None:
    """Classify field lifecycle by fitting a logistic curve to cumulative counts.

    Returns {phase, carrying_capacity, midpoint_year, fit_quality} where phase is one of
    "emerging", "growing", "mature", "saturating". Returns None if there are fewer than 4
    data points or scipy is unavailable.
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

    return {
        "phase": phase,
        "carrying_capacity": round(K, 1),
        "midpoint_year": round(t0, 1),
        "growth_rate": round(r, 3),
        "fit_quality": round(r_squared, 3),
        "progress": round(progress, 3),
    }


def analyze_publication_trends(db: Session, project_id: int) -> dict:
    project = db.get(SearchProject, project_id)
    if not project:
        return dict(_EMPTY)
    query_ids = [q.id for q in project.queries]
    if not query_ids:
        return dict(_EMPTY)
    pubs = db.query(Publication.year).filter(
        Publication.query_id.in_(query_ids), Publication.year.isnot(None), Publication.excluded == False).all()
    if not pubs:
        return dict(_EMPTY)

    yearly_counter = Counter(int(year) for (year,) in pubs if year is not None)
    yearly_items = sorted(yearly_counter.items())
    yearly_counts = [{"year": year, "count": count} for year, count in yearly_items]
    counts = [count for _, count in yearly_items]

    growth_rates = []
    for i in range(1, len(counts)):
        prev = counts[i - 1]
        rate = ((counts[i] - prev) / prev * 100) if prev > 0 else 0
        growth_rates.append({"year": yearly_items[i][0], "rate": round(rate, 1)})

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
    }
