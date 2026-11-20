"""Reporting aids adapted from BIBLIO Table 3 (doi:10.1186/s13643-023-02410-2)
and PRISMA-S (doi:10.1186/s13643-020-01542-z).
"""
import re
from collections.abc import Sequence
from datetime import date

from bibmeded.models import MethodologyStep, SearchQuery

MISSING = "not recorded"
BIBLIO_DOI = "https://doi.org/10.1186/s13643-023-02410-2"
PRISMA_S_DOI = "https://doi.org/10.1186/s13643-020-01542-z"

# Short paraphrases in the order used in Table 3.
BIBLIO_ITEMS = (
    "Identify the review as bibliometric in its title.",
    "State the topic and time span in the title.",
    "Summarize the context, methods, findings, and conclusions in the abstract.",
    "Explain the rationale and summarize existing knowledge.",
    "Specify the review objectives or questions.",
    "Identify all sources consulted.",
    "Document search terms, dates, and restrictions.",
    "Explain the review's time window and its rationale.",
    "State the criteria for including and excluding records.",
    "Explain screening, refinement, and duplicate removal.",
    "Describe any quality appraisal and who performed it.",
    "Explain the analysis and synthesis methods.",
    "Show study selection and describe the resulting corpus.",
    "Report maps, trends, and relevant bibliometric indicators.",
    "Organize and tabulate results by relevant themes or groups.",
    "Integrate findings and identify gaps or hypotheses.",
    "Summarize the principal evidence in accessible language.",
    "Interpret the findings in light of the results.",
    "Discuss strengths and limitations.",
    "Relate conclusions and implications to the review question.",
)

ANALYSIS_METRICS = {
    "publications": "publication counts by year and growth",
    "authors": "author output and productivity",
    "countries": "country and institution output and collaboration",
    "journals": "journal output and Bradford zones",
    "keywords": "keyword frequency and co-occurrence",
    "citations": "citation counts and citation networks",
}


def _value(value: object) -> str:
    return MISSING if value is None or value == "" else str(value)


def _table_cell(value: str) -> str:
    # CommonMark punctuation must stay literal even when a query contains markup.
    flat = " ".join(value.splitlines())
    return re.sub(r'[&<>`*_~|\[\]\\!]', lambda m: f"&#{ord(m[0])};", flat)


def _search_steps(steps: Sequence[MethodologyStep]) -> list[MethodologyStep]:
    return [step for step in steps if step.phase == "search"]


def _query(step: MethodologyStep, queries: dict[int, SearchQuery]) -> str | None:
    query = queries.get(step.query_id)
    return (step.parameters or {}).get("query") or (query.query_string if query else None)


def _search_date(step: MethodologyStep) -> str:
    params = step.parameters or {}
    if params.get("synthetic"):
        return "not applicable (synthetic data)"
    return _value(params.get("searched_at"))


def _limits(params: dict) -> str:
    if params.get("synthetic"):
        return "not applicable (synthetic data)"
    if "year_filters" not in params:
        return MISSING
    filters = params["year_filters"]
    if not filters:
        return "no separate year filters; see query text for inline restrictions"
    return "; ".join(f"{label}: {filters[key]}" for key, label in (
        ("year_start", "start year"), ("year_end", "end year"),
    ) if filters.get(key))


def _deduplication(steps: Sequence[MethodologyStep]) -> str:
    descriptions = []
    for step in steps:
        if step.phase == "dedup":
            params = step.parameters or {}
            method = params.get("method") or params.get("matched_by") or step.action
            fields = f" ({params['fields']})" if params.get("fields") else ""
            descriptions.append(f"Search {step.query_id}: {method}{fields}, {step.records_affected} removed")
    return "; ".join(descriptions) or MISSING


def generate_biblio(
    project_name: str,
    steps: Sequence[MethodologyStep],
    *,
    queries: Sequence[SearchQuery] = (),
    date_start: date | None = None,
    date_end: date | None = None,
    exclusions: dict[tuple[str | None, str | None], int] | None = None,
    included_count: int | None = None,
    analyses: Sequence[tuple[str, str | None]] = (),
) -> str:
    searches = _search_steps(steps)
    by_id = {q.id: q for q in queries}
    sources = ", ".join(dict.fromkeys(step.source for step in searches))
    strategies = "; ".join(
        f"Search {s.query_id} ({s.source}): {_value(_query(s, by_id))}; date: {_search_date(s)}"
        for s in searches
    )
    ranges = "; ".join(
        f"Search {s.query_id}: {_limits(s.parameters or {})}" for s in searches
    )
    period = []
    if date_start or date_end:
        period.append(f"Project coverage: {_value(date_start)} to {_value(date_end)}")
    if ranges:
        period.append(f"Separate search filters: {ranges}")
    decisions = "; ".join(
        f"{_value(stage)} / {_value(reason)}: {count}"
        for (stage, reason), count in sorted((exclusions or {}).items(), key=lambda entry: tuple(
            value or "" for value in entry[0]
        ))
    )
    methods = "; ".join(dict.fromkeys(
        f"{kind} ({ANALYSIS_METRICS.get(kind, MISSING)}); BibMedEd version: {_value(version)}"
        for kind, version in analyses
    ))
    values = {
        6: sources,
        7: strategies,
        8: "; ".join(period) + f"; rationale: {MISSING}" if period else "",
        9: f"Recorded exclusion outcomes: {decisions}; full eligibility protocol: {MISSING}" if decisions else "",
        10: f"Logged deduplication: {_deduplication(steps)}; exclusions by stage and reason: {_value(decisions)}"
            if decisions or any(step.phase == "dedup" for step in steps) else "",
        12: methods,
        13: f"Included records: {included_count}. See the PRISMA flow diagram for selection counts."
            if included_count is not None and (searches or included_count) else "",
    }
    lines = [
        "# BIBLIO reporting worksheet", "",
        f"Project: {_table_cell(project_name)}", "",
        f"Item summaries adapted from [Montazeri et al., Table 3]({BIBLIO_DOI}) "
        "([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)).",
        "Fill in manuscript locations and any missing details before submission.",
        "",
    ]
    if any((step.parameters or {}).get("synthetic") for step in searches):
        lines.extend(["This project includes a synthetic demonstration search.", ""])
    lines += ["| No. | Checklist item (summary) | Project evidence | Reported on page / section |",
              "| --- | --- | --- | --- |"]
    for number, item in enumerate(BIBLIO_ITEMS, 1):
        lines.append(f"| {number} | {item} | {_table_cell(_value(values.get(number)))} | |")
    return "\n".join(lines) + "\n"


def generate_prisma_s(
    project_name: str, steps: Sequence[MethodologyStep], *, queries: Sequence[SearchQuery] = (),
) -> str:
    by_id = {q.id: q for q in queries}
    sections = [
        f"PRISMA-S search appendix\nProject: {project_name}\n"
        f"Adapted from Rethlefsen et al. ({PRISMA_S_DOI}), items 1, 8, 9, 13, 15, and 16.\n"
        "Review external searches, adapter-specific syntax, and limit justifications before submission."
    ]
    for step in _search_steps(steps):
        params = step.parameters or {}
        cap = params.get("capped")
        query = _value(_query(step, by_id))
        notes = [
            f"Search {step.query_id} — {step.source}",
            f"Platform / method: {step.action}",
            f"Search date: {_search_date(step)}",
            f"Separate publication-year filters: {_limits(params)}",
            f"Upstream matches: {_value(params.get('upstream_total'))}",
            f"Retrieved identifiers: {_value(params.get('retrieved_ids'))}",
            f"Configured retrieval cap: {_value(params.get('max_results'))}",
            f"Retrieval truncated: {'yes' if cap else 'no' if cap is False else MISSING}",
        ]
        if params.get("synthetic"):
            notes.append(f"Synthetic input records: {step.records_out}. No upstream search was run.")
        elif "upstream_total" not in params:
            notes.append(f"Legacy methodology search count (scope unspecified): {step.records_out}")
        notes.append("Exact stored query submitted to BibMedEd (sample queries are illustrative):")
        sections.append("\n".join(notes) + "\n" + query)
    if len(sections) == 1:
        sections.append("Searches: not recorded")
    sections.append(f"Deduplication steps recorded in the methodology log: {_deduplication(steps)}")
    return "\n\n".join(sections) + "\n"
