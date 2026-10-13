"""Lotka's law of author productivity.

Lotka, A. J. (1926). The frequency distribution of scientific productivity.
Journal of the Washington Academy of Sciences, 16(12), 317-323.

Pao, M. L. (1985). Lotka's law: a testing procedure. Information Processing &
Management, 21(4), 305-320.
"""

import math
from collections import Counter
from collections.abc import Iterable

MIN_PRODUCTIVITY_LEVELS = 3
KS_SIGNIFICANCE_LEVEL = 0.01
KS_COEFFICIENT = 1.63
KS_MIN_AUTHORS = 36
# The gate is on the alpha the caller sees, which is rounded to four decimals.
ALPHA_GATE_TOLERANCE = 5e-5
# Pao truncates the zeta series at P = 20 terms and closes it with an
# Euler-Maclaurin remainder; at alpha = 2 this matches 6/pi^2 to five decimals.
_PAO_SERIES_TERMS = 20

LOTKA_METHOD = (
    "Lotka's law (Lotka 1926): least-squares fit of log10(authors) on log10(papers) over every "
    "productivity level; Kolmogorov-Smirnov test against the fitted distribution (Pao 1985)"
)
LOTKA_PARAMETERS = {
    "counting": "complete",
    "min_productivity_levels": MIN_PRODUCTIVITY_LEVELS,
    "significance_level": KS_SIGNIFICANCE_LEVEL,
    "ks_coefficient": KS_COEFFICIENT,
    "ks_min_authors": KS_MIN_AUTHORS,
}

_NO_AUTHORS_REASON = "No authors in the included records, so there is no productivity distribution to fit."
_FLAT_REASON = (
    "Every productivity level has the same number of authors, so the log-log fit has no variance "
    "to explain and R^2 is undefined."
)


def _too_few_levels_reason(levels: int) -> str:
    return (
        f"At least {MIN_PRODUCTIVITY_LEVELS} distinct productivity levels (papers per author) are "
        f"needed to fit Lotka's law; found {levels}. Two points always fit a line exactly."
    )


def _log_log_regression(levels: Counter) -> tuple[float, float, float]:
    """Least squares of log10(authors) on log10(papers): returns (alpha, C, R^2) with
    authors = C / papers^alpha. Callers guarantee >= 2 x values and non-constant y."""
    xs = [math.log10(n) for n in levels]
    ys = [math.log10(a) for a in levels.values()]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in ys)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return -slope, 10 ** (mean_y - slope * mean_x), sxy * sxy / (sxx * syy)


def _pao_constant(alpha: float) -> float:
    """Share of authors with exactly one paper under Lotka's law, 1 / zeta(alpha) (Pao 1985)."""
    p = _PAO_SERIES_TERMS
    series = sum(1 / x**alpha for x in range(1, p))
    remainder = 1 / ((alpha - 1) * p ** (alpha - 1)) + 1 / (2 * p**alpha) + alpha / (24 * (p - 1) ** (alpha + 1))
    return 1 / (series + remainder)


def _ks_against_lotka(levels: Counter, total: int, alpha: float) -> dict:
    """Pao's one-sample K-S test: the largest gap between the observed and expected
    cumulative author shares, checked at every integer paper count up to the maximum."""
    result = {
        "test": "kolmogorov-smirnov",
        "significance_level": KS_SIGNIFICANCE_LEVEL,
        "D": None,
        "critical_value": None,
        "consistent_with_lotka": None,
        "expected_single_paper_share": None,
        "reason": None,
    }
    if alpha <= 1 + ALPHA_GATE_TOLERANCE:
        return {
            **result,
            "reason": (
                f"The fitted alpha is {round(alpha, 4)}; the Lotka distribution only sums to 1 for "
                "alpha > 1, so there is no expected distribution to test against."
            ),
        }
    single_paper_share = _pao_constant(alpha)
    observed = expected = d_max = 0.0
    for papers in range(1, max(levels) + 1):
        observed += levels.get(papers, 0) / total
        expected += single_paper_share / papers**alpha
        d_max = max(d_max, abs(observed - expected))
    result = {**result, "D": round(d_max, 4), "expected_single_paper_share": round(single_paper_share, 4)}
    if total < KS_MIN_AUTHORS:
        return {
            **result,
            "reason": (
                f"The critical value {KS_COEFFICIENT}/sqrt(N) is asymptotic and needs more than "
                f"{KS_MIN_AUTHORS - 1} authors; found {total}, so D is reported without a verdict."
            ),
        }
    critical = KS_COEFFICIENT / math.sqrt(total)
    return {**result, "critical_value": round(critical, 4), "consistent_with_lotka": d_max < critical}


def fit_lotka(pub_counts: Iterable[int]) -> dict:
    """Fit Lotka's law to per-author paper counts (complete counting: every author of a
    paper is credited with it).

    Lotka (1926) observed that the number of authors with n papers is about C / n^alpha,
    with alpha close to 2. ``alpha`` and ``C`` come from least squares on the log-log
    productivity distribution over all levels, with no tail cutoff; ``C`` is in authors,
    i.e. the predicted number of single-paper authors. Goodness of fit follows Pao (1985):
    a Kolmogorov-Smirnov test of the observed distribution against the Lotka distribution
    with the fitted alpha, at the 0.01 level.

    ``fit`` is ``None`` with a ``reason`` when there are fewer than 3 productivity levels
    or every level has the same number of authors. ``distribution`` always lists every
    author, so ``total_authors`` reconciles with the authors analysis.
    """
    levels = Counter(pub_counts)
    if any(papers < 1 for papers in levels):
        raise ValueError("Paper counts per author must be positive integers.")
    total = sum(levels.values())
    result = {
        "distribution": [{"papers": papers, "authors": levels[papers]} for papers in sorted(levels)],
        "total_authors": total,
        "productivity_levels": len(levels),
        "fit": None,
        "reason": None,
        "method": LOTKA_METHOD,
        "parameters": dict(LOTKA_PARAMETERS),
    }
    if total == 0:
        return {**result, "reason": _NO_AUTHORS_REASON}
    if len(levels) < MIN_PRODUCTIVITY_LEVELS:
        return {**result, "reason": _too_few_levels_reason(len(levels))}
    if len(set(levels.values())) == 1:
        return {**result, "reason": _FLAT_REASON}

    alpha, constant, r_squared = _log_log_regression(levels)
    return {
        **result,
        "fit": {
            "alpha": round(alpha, 4),
            "C": round(constant, 2),
            "r_squared": round(r_squared, 4),
            "goodness_of_fit": _ks_against_lotka(levels, total, alpha),
        },
    }
