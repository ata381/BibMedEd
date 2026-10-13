"""Pure-function generators for the export endpoints.

Each function returns its full content as text/bytes so callers (router endpoints, the
bundle endpoint, tests) can compose them without going through Starlette `StreamingResponse`.
"""

import csv
import io
import json
import re
import zipfile
from collections import Counter
from datetime import date, datetime, timezone

from bibmeded.models import Publication, ScreeningDecision
from bibmeded.models import Publication
from bibmeded.models.author import Affiliation
from bibmeded.models.keyword import KeywordType
from bibmeded.models.methodology import MethodologyStep
from bibmeded.services.cleaning import extract_country
from bibmeded.services.prisma import ExclusionSummary, compute_counts, render_svg, summarize_exclusions
from bibmeded.services.screening import BULK_EXCLUDE_PHASE, BULK_EXCLUDE_SOURCE, ScreeningDecisionLog


_PHASE_LABELS = {
    "search": "SEARCH STRATEGY",
    "fetch": "DATA COLLECTION",
    "dedup": "DEDUPLICATION",
    "enrichment": "ENRICHMENT",
    "exclusion": "EXCLUSION",
}


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    return re.sub(r"[\s_]+", "-", slug)[:50]


# Leading characters that Excel/Sheets/LibreOffice interpret as the start of a
# formula. Bibliographic fields (titles, author names, journal names, keywords)
# come from external APIs and are attacker-influenced, so any value starting
# with one of these must be neutralized before it's written to a CSV cell —
# otherwise opening the export in a spreadsheet app can execute the "formula"
# (OWASP CSV Injection / Formula Injection).
_CSV_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Prefix a leading apostrophe onto values that would otherwise be
    interpreted as spreadsheet formulas, per the standard OWASP CSV escaping
    mitigation. The apostrophe forces the cell to be treated as text.
    """
    if value and value[0] in _CSV_FORMULA_TRIGGER_CHARS:
        return "'" + value
    return value


def generate_csv(pubs: list[Publication]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["PMID", "DOI", "Title", "Authors", "Journal", "Year", "Citations", "Keywords", "Abstract"])
    for pub in pubs:
        writer.writerow([
            _csv_safe(pub.pmid or ""),
            _csv_safe(pub.doi or ""),
            _csv_safe(pub.title or ""),
            _csv_safe("; ".join(a.name for a in pub.authors)),
            _csv_safe(pub.journal.name if pub.journal else ""),
            pub.year or "",
            pub.citation_count if pub.citation_count is not None else "",
            _csv_safe("; ".join(k.term for k in pub.keywords)),
            _csv_safe((pub.abstract or "").replace("\n", " ")),
        ])
    return output.getvalue()


EXPORT_SCHEMA_VERSION = "1.0"


def _publication_to_dict(pub: Publication) -> dict:
    return {
        "pmid": pub.pmid,
        "doi": pub.doi,
        "title": pub.title,
        "abstract": pub.abstract,
        "year": pub.year,
        "publication_type": pub.publication_type,
        "source_database": pub.source_database,
        "citation_count": pub.citation_count,
        "excluded": pub.excluded,
        "exclusion_reason": pub.exclusion_reason,
        "screening_stage": pub.screening_stage,
        "journal_name": pub.journal.name if pub.journal else None,
        "journal_issn": pub.journal.issn if pub.journal else None,
        "authors": [
            {"name": a.name, "orcid": a.orcid}
            for a in pub.authors
        ],
        "keywords": [k.term for k in pub.keywords],
    }


def generate_json(project_name: str, pubs: list[Publication]) -> str:
    """Bulk JSON export with a versioned schema for downstream pipelines.

    Shape: ``{schema_version, project, generated, count, publications: [...]}``.
    Each publication entry is the dict returned by ``_publication_to_dict``. Encoded
    with ``ensure_ascii=False`` so non-ASCII titles/abstracts (Turkish, Chinese,
    Greek) round-trip cleanly.
    """
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "project": project_name,
        "generated": date.today().isoformat(),
        "count": len(pubs),
        "publications": [_publication_to_dict(p) for p in pubs],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


_LINE_BREAKS = re.compile(r"[\r\n\v\f\x1c-\x1e\x85\u2028\u2029]+")


def _ris_safe(value: str) -> str:
    """Replace embedded line breaks in a field value before writing it into an RIS
    or WoS tag line. Both formats are newline-delimited, so an unescaped newline in an
    attacker-influenced field (title/author/journal/keyword) lets a malicious
    record inject arbitrary tag lines — including a fake ``ER  - `` that
    terminates the record early or a fake ``TY  - JOUR`` that starts a new one.
    Every separator Python's ``str.splitlines`` honours is covered, not only CR/LF,
    so readers with wider line-break rules cannot be split either.
    """
    return _LINE_BREAKS.sub(" ", value).strip()


def generate_ris(pubs: list[Publication]) -> str:
    lines: list[str] = []
    for pub in pubs:
        lines.append("TY  - JOUR")
        lines.append(f"TI  - {_ris_safe(pub.title)}")
        for author in pub.authors:
            lines.append(f"AU  - {_ris_safe(author.name)}")
        if pub.journal:
            lines.append(f"JO  - {_ris_safe(pub.journal.name)}")
        if pub.year:
            lines.append(f"PY  - {pub.year}")
        if pub.doi:
            lines.append(f"DO  - {_ris_safe(pub.doi)}")
        lines.append(f"AN  - {pub.pmid}")
        if pub.abstract:
            lines.append(f"AB  - {_ris_safe(pub.abstract)}")
        for kw in pub.keywords:
            lines.append(f"KW  - {_ris_safe(kw.term)}")
        lines.append("ER  - ")
        lines.append("")
    return "\n".join(lines)


# Genuine Web of Science plain-text exports start with a UTF-8 BOM. Writing one keeps
# the file in the shape VOSviewer and bibliometrix already parse, and stops tools that
# fall back to the platform code page from misreading non-ASCII names.
_WOS_BOM = "\ufeff"
_WOS_HEADER = ("FN Clarivate Analytics Web of Science", "VR 1.0")
_WOS_CONTINUATION = "   "
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def _wos_tag(tag: str, values: list[str]) -> list[str]:
    cleaned = [v for v in (_ris_safe(value) for value in values) if v]
    if not cleaned:
        return []
    return [f"{tag} {cleaned[0]}", *(f"{_WOS_CONTINUATION}{v}" for v in cleaned[1:])]


def _wos_name_parts(name: str, source_database: str) -> tuple[str, str]:
    """Split a stored author name into (surname, given names).

    PubMed stores persons as "Surname, Given" and collective authors without a
    comma, so a comma-less PubMed name is kept whole. Other adapters store
    "Given Surname", where the last token is taken as the surname.
    """
    name = " ".join(_ris_safe(name).split())
    if "," in name:
        surname, given = name.split(",", 1)
        return surname.strip(), given.strip()
    if source_database == "pubmed" or " " not in name:
        return name, ""
    given, surname = name.rsplit(" ", 1)
    return surname, given


def _wos_initials(given: str) -> str:
    return "".join(token[0].upper() for token in re.split(r"[\s.\-]+", given) if token)


def _wos_short_name(surname: str, given: str) -> str:
    initials = _wos_initials(given)
    return f"{surname}, {initials}" if initials else surname


def _wos_full_name(surname: str, given: str) -> str:
    return f"{surname}, {given}" if given else surname


def _wos_address(affiliation: Affiliation) -> str:
    """One C1 address: the stored affiliation text, the stored country appended when
    the text does not already name it, and a closing period.

    bibliometrix joins C1 lines with spaces and splits addresses on ".", and VOSviewer
    reads the country from the last comma-separated part, so both the period and a
    trailing country are load-bearing. The "already names it" test reuses
    ``extract_country`` so an alias ("England" stored as "UK") is not appended twice.
    """
    address = _ris_safe(affiliation.name or "").rstrip(". ")
    if not address:
        return ""
    country = _ris_safe(affiliation.country or "")
    if country and extract_country(address) != country:
        address = f"{address}, {country}"
    return f"{address}."


def _wos_addresses(pub: Publication, short_names: list[str]) -> list[str]:
    authors_by_address: dict[str, list[str]] = {}
    for author, short_name in zip(pub.authors, short_names):
        if not short_name:
            continue
        for affiliation in author.affiliations:
            address = _wos_address(affiliation)
            if not address:
                continue
            names = authors_by_address.setdefault(address, [])
            if short_name not in names:
                names.append(short_name)
    return [f"[{'; '.join(names)}] {address}" for address, names in authors_by_address.items()]


def _wos_keywords(pub: Publication, kind: KeywordType) -> str:
    terms = (_ris_safe(k.term or "") for k in pub.keywords if k.type == kind)
    return "; ".join(term for term in terms if term)


def _wos_corpus_index(pubs: list[Publication]) -> dict[str, Publication]:
    """Exported records that have a DOI, keyed by lowercased DOI and source-native id."""
    index: dict[str, Publication] = {}
    for pub in pubs:
        if not pub.doi:
            continue
        index[pub.doi.lower()] = pub
        if pub.pmid:
            index[pub.pmid.lower()] = pub
    return index


def _wos_cited_reference_form(cited: Publication) -> str:
    """WoS cited-reference string ``SURNAME I, YEAR, SOURCE, DOI x`` for a record in the export.

    bibliometrix's histNetwork matches each CR entry against a record's SR (first
    author, year, source) plus its DOI, so in-corpus citations need this form; a bare
    ``DOI x`` never produces a local citation.
    """
    parts: list[str] = []
    first_author = next((a for a in cited.authors if _ris_safe(a.name or "")), None)
    if first_author is not None:
        surname, given = _wos_name_parts(first_author.name, cited.source_database)
        parts.append(f"{surname} {_wos_initials(given)}".strip().upper())
    if cited.year:
        parts.append(str(cited.year))
    source = _ris_safe(cited.journal.name or "") if cited.journal else ""
    if source:
        parts.append(source.upper())
    parts.append(f"DOI {cited.doi.lower()}")
    return ", ".join(parts)


def _wos_references(pub: Publication) -> list:
    """The JSON column only means something as a list; a legacy string or scalar
    value would otherwise be iterated character by character."""
    return pub.external_references if isinstance(pub.external_references, list) else []


def _wos_cited_references(pub: Publication, corpus_index: dict[str, Publication]) -> list[str]:
    """CR entries for ``pub``.

    ``external_references`` holds source-native identifiers. A reference that resolves
    to a record in this export with a DOI (by DOI or by source-native id, the same
    matching the citation analysis uses) gets the full WoS form; any other DOI is
    written as bare ``DOI x``. The rest have no WoS form, so ``NR`` carries the full
    count and the bundle manifest reports the shortfall.
    """
    cited: list[str] = []
    seen_dois: set[str] = set()
    for raw_ref in _wos_references(pub):
        ref = str(raw_ref).strip().lower()
        target = corpus_index.get(ref)
        if target is not None:
            doi = target.doi.lower()
        elif _DOI_PATTERN.match(ref):
            doi = ref
        else:
            continue
        if doi in seen_dois:
            continue
        seen_dois.add(doi)
        cited.append(_wos_cited_reference_form(target) if target is not None else f"DOI {doi}")
    return cited


def wos_reference_coverage(pubs: list[Publication]) -> tuple[int, int]:
    """(cited references written to CR, references the sources reported)."""
    corpus_index = _wos_corpus_index(pubs)
    written = sum(len(_wos_cited_references(pub, corpus_index)) for pub in pubs)
    reported = sum(len(_wos_references(pub)) for pub in pubs)
    return written, reported


def _wos_record(pub: Publication, corpus_index: dict[str, Publication]) -> list[str]:
    name_parts = [_wos_name_parts(author.name or "", pub.source_database) for author in pub.authors]
    short_names = [_wos_short_name(surname, given) for surname, given in name_parts]
    references = _wos_references(pub)
    journal = pub.journal
    return [
        "PT J",
        *_wos_tag("AU", short_names),
        *_wos_tag("AF", [_wos_full_name(surname, given) for surname, given in name_parts]),
        *_wos_tag("TI", [pub.title or ""]),
        *_wos_tag("SO", [journal.name if journal else ""]),
        *_wos_tag("DT", [pub.publication_type or ""]),
        *_wos_tag("DE", [_wos_keywords(pub, KeywordType.author_keyword)]),
        *_wos_tag("ID", [_wos_keywords(pub, KeywordType.mesh_term)]),
        *_wos_tag("AB", [pub.abstract or ""]),
        *_wos_tag("C1", _wos_addresses(pub, short_names)),
        *_wos_tag("CR", _wos_cited_references(pub, corpus_index)),
        *_wos_tag("NR", [str(len(references))] if references else []),
        *_wos_tag("TC", [str(pub.citation_count)] if pub.citation_count is not None else []),
        *_wos_tag("SN", [journal.issn or ""] if journal else []),
        *_wos_tag("EI", [journal.e_issn or ""] if journal else []),
        *_wos_tag("PY", [str(pub.year)] if pub.year else []),
        *_wos_tag("DI", [pub.doi or ""]),
        *_wos_tag("UT", [f"{pub.source_database.upper()}:{pub.pmid}"] if pub.pmid else []),
        *_wos_tag("PM", [pub.pmid] if pub.source_database == "pubmed" else []),
        "ER",
        "",
    ]


def generate_wos_plaintext(pubs: list[Publication]) -> str:
    """Web of Science tagged plain text, the input VOSviewer and bibliometrix
    (``convert2df(dbsource="wos", format="plaintext")``) read.

    Every value is one line; multi-valued fields (AU, AF, C1, CR) put one value per
    line with 3-space continuation lines, records end with ``ER`` and a blank line,
    and the file ends with ``EF``. Field mapping and known gaps are documented in
    ``docs/scripting.md``.
    """
    corpus_index = _wos_corpus_index(pubs)
    lines = [*_WOS_HEADER]
    for pub in pubs:
        lines.extend(_wos_record(pub, corpus_index))
    lines.append("EF")
    return _WOS_BOM + "\n".join(lines) + "\n"


EXCLUSION_REASON_LABELS = {
    "wrong_study_design": "Wrong study design",
    "wrong_population": "Wrong population",
    "wrong_intervention": "Wrong intervention",
    "wrong_outcome": "Wrong outcome",
    "not_peer_reviewed": "Not peer-reviewed (conference abstract, preprint, editorial)",
    "non_english": "Non-English language",
    "duplicate": "Duplicate not caught by automated dedup",
    "fulltext_unavailable": "Full-text not retrievable",
    "other": "Other / unspecified",
}


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _reason_count_lines(by_reason: dict[str, int], indent: str = "    ") -> list[str]:
    return [
        f"{indent}{EXCLUSION_REASON_LABELS.get(reason, reason)}: {n}"
        for reason, n in sorted(by_reason.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _screening_stage_lines(exclusion_summary: ExclusionSummary | None) -> list[str]:
    """Current screening state per PRISMA 2020 stage, mirroring the flow diagram."""
    staged = summarize_exclusions(exclusion_summary)
    lines = [
        "SCREENING DECISIONS BY STAGE (PRISMA 2020 item 16a)",
        f"  Title/abstract screening: {_plural(staged.title_abstract_total, 'record')} excluded",
        *_reason_count_lines(staged.title_abstract_by_reason),
        f"  Full-text retrieval: {_plural(staged.not_retrieved, 'report')} not retrieved",
        f"  Full-text eligibility: {_plural(staged.full_text_total, 'report')} excluded",
        *_reason_count_lines(staged.full_text_by_reason),
    ]
    if staged.unrecorded_not_retrieved:
        lines.append(
            f"  Note: {staged.unrecorded_stage} exclusion(s) have no recorded screening stage: "
            f"{staged.unrecorded_not_retrieved} with reason full-text unavailable are counted as "
            "reports not retrieved, "
            f"{staged.unrecorded_stage - staged.unrecorded_not_retrieved} at title/abstract."
        )
    elif staged.unrecorded_stage:
        lines.append(
            f"  Note: {staged.unrecorded_stage} exclusion(s) have no recorded screening stage "
            "and are counted at title/abstract."
        )
    lines.append("")
    return lines


DECISIONS_REVISION = "0006_screening_decisions"
_STAGE_LABELS = {"title_abstract": "Title/abstract", "full_text": "Full text", None: "No stage recorded"}
_NO_REASON_LABEL = "No reason recorded"
_SCREENING_DECISION_CSV_HEADER = [
    "decision_id", "decided_at_utc", "reviewer", "source", "run_id", "action", "criteria",
    "publication_id", "pmid", "doi",
    "previous_excluded", "previous_exclusion_reason", "previous_screening_stage",
    "excluded", "exclusion_reason", "screening_stage",
]


def _as_utc(moment: datetime) -> datetime:
    # decided_at is written as UTC; SQLite returns it without tzinfo.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _utc_stamp(moment: datetime, timespec: str = "seconds") -> str:
    return _as_utc(moment).isoformat(timespec=timespec).replace("+00:00", "Z")


def _decision_action(decision: ScreeningDecision) -> str:
    if decision.excluded == decision.previous_excluded:
        return "change"
    return "exclude" if decision.excluded else "re-include"


def _criteria_json(criteria: dict | None) -> str:
    return "" if criteria is None else json.dumps(criteria, sort_keys=True)


def _criteria_text(criteria: dict | None) -> str:
    if criteria and set(criteria) == {"citation_threshold"}:
        return f"citation count missing or at most {criteria['citation_threshold']}"
    return f"criteria {_criteria_json(criteria) or 'not recorded'}"


def _stage_label(stage: str | None) -> str:
    return _STAGE_LABELS.get(stage, stage)


def _decision_count_lines(decisions: tuple[ScreeningDecision, ...]) -> list[str]:
    actions = Counter(_decision_action(d) for d in decisions)
    return [
        f"  Decisions logged: {len(decisions)}",
        f"    Exclusions: {actions['exclude']}",
        f"    Reversals (excluded record re-included): {actions['re-include']}",
        f"    Reason or stage changes: {actions['change']}",
        f"  First decision: {_utc_stamp(min(_as_utc(d.decided_at) for d in decisions))}",
        f"  Last decision: {_utc_stamp(max(_as_utc(d.decided_at) for d in decisions))}",
    ]


def _exclusion_decision_lines(decisions: tuple[ScreeningDecision, ...]) -> list[str]:
    by_stage: dict[str | None, Counter] = {}
    for decision in decisions:
        if decision.excluded:
            reason = decision.exclusion_reason or _NO_REASON_LABEL
            by_stage.setdefault(decision.screening_stage, Counter())[reason] += 1
    if not by_stage:
        return []
    stage_order = [stage for stage in _STAGE_LABELS if stage in by_stage]
    stage_order += sorted(stage for stage in by_stage if stage not in _STAGE_LABELS)
    lines = ["  Exclusion decisions by stage and reason:"]
    for stage in stage_order:
        lines.append(f"    {_stage_label(stage)}: {sum(by_stage[stage].values())}")
        lines.extend(_reason_count_lines(dict(by_stage[stage]), indent="      "))
    return lines


def _bulk_settings_text(reason: str | None, stage: str | None, reviewer: str | None) -> str:
    reason_label = EXCLUSION_REASON_LABELS.get(reason, reason) if reason else _NO_REASON_LABEL
    return f"(reason: {reason_label}; stage: {_stage_label(stage)}; reviewer: {reviewer or 'none recorded'})"


def _bulk_step_lines(step: MethodologyStep, logged_rows: int) -> list[str]:
    params = step.parameters or {}
    criteria = {"citation_threshold": params["citation_threshold"]} if "citation_threshold" in params else None
    lines = [
        f"    {_utc_stamp(step.timestamp)} (run {params.get('run_id') or 'id not recorded'}): "
        f"{params.get('matched')} matched, {params.get('excluded')} excluded, {params.get('skipped')} skipped; "
        f"{_criteria_text(criteria)} "
        f"{_bulk_settings_text(params.get('reason'), params.get('screening_stage'), params.get('reviewer'))}"
    ]
    if logged_rows != params.get("excluded"):
        lines.append(
            f"      Note: {_plural(logged_rows, 'decision row')} {'carries' if logged_rows == 1 else 'carry'} "
            "this run id, "
            f"but the step records {params.get('excluded')} exclusion(s)."
        )
    return lines


def _bulk_rows_lines(run_id: str | None, members: list[ScreeningDecision]) -> list[str]:
    first = members[0]
    run_label = f"run {run_id}, no methodology step recorded" if run_id else "run id not recorded"
    return [
        f"    {_utc_stamp(first.decided_at)} ({run_label}): {_plural(len(members), 'record')} excluded with "
        f"{_criteria_text(first.criteria)} "
        f"{_bulk_settings_text(first.exclusion_reason, first.screening_stage, first.reviewer)}"
    ]


def _bulk_exclusion_lines(decisions: tuple[ScreeningDecision, ...], bulk_steps: list[MethodologyStep]) -> list[str]:
    """One entry per bulk request: from its methodology step when there is one
    (so a run that excluded nothing still shows), else from its decision rows."""
    rows_by_run: dict[str | tuple, list[ScreeningDecision]] = {}
    for d in decisions:
        if d.source != BULK_EXCLUDE_SOURCE:
            continue
        # Rows without a run id fall back to their shared request timestamp.
        key = d.run_id or (
            _as_utc(d.decided_at), _criteria_json(d.criteria), d.exclusion_reason, d.screening_stage, d.reviewer,
        )
        rows_by_run.setdefault(key, []).append(d)
    entries: list[tuple[datetime, list[str]]] = []
    for step in bulk_steps:
        logged_rows = len(rows_by_run.pop((step.parameters or {}).get("run_id"), []))
        entries.append((_as_utc(step.timestamp), _bulk_step_lines(step, logged_rows)))
    for key, members in rows_by_run.items():
        run_id = key if isinstance(key, str) else None
        entries.append((_as_utc(members[0].decided_at), _bulk_rows_lines(run_id, members)))
    if not entries:
        return []
    return ["  Bulk exclusions:", *(line for _, group in sorted(entries, key=lambda e: e[0]) for line in group)]


def _reviewer_lines(decisions: tuple[ScreeningDecision, ...]) -> list[str]:
    labels = sorted({d.reviewer for d in decisions if d.reviewer is not None})
    unlabelled = sum(1 for d in decisions if d.reviewer is None)
    return [
        f"  Reviewer labels: {', '.join(labels) if labels else 'none recorded'}",
        f"  Decisions without a reviewer label: {unlabelled}",
    ]


def _screening_decision_lines(decision_log: ScreeningDecisionLog, bulk_steps: list[MethodologyStep]) -> list[str]:
    """Summary of the append-only screening decision log and of every bulk
    exclusion request, with what the log cannot show."""
    decisions = decision_log.decisions
    lines = ["SCREENING DECISION HISTORY (audit trail)"]
    if decisions:
        lines += _decision_count_lines(decisions)
        lines += _exclusion_decision_lines(decisions)
    else:
        lines.append("  Decisions logged: 0")
    lines += _bulk_exclusion_lines(decisions, bulk_steps)
    if decisions:
        lines += _reviewer_lines(decisions)
        lines.append("  Per-decision log: the screening-decisions CSV in the export bundle.")
    lines.append(
        "  Not backfilled: decisions made before the audit trail existed "
        f"(Alembic revision {DECISIONS_REVISION}) were not recorded."
    )
    unlogged = decision_log.unlogged_exclusions
    if unlogged:
        verb = "has" if unlogged == 1 else "have"
        lines.append(f"    {_plural(unlogged, 'currently excluded record')} {verb} no logged decision.")
    lines.append("")
    return lines


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _lotka_lines(lotka: dict) -> list[str]:
    """Author productivity step: method, parameters and the fit or the reason it is missing."""
    params = lotka["parameters"]
    lines = [
        "AUTHOR PRODUCTIVITY (Lotka's law)",
        f"  Method: {lotka['method']}",
        f"  Parameters: {params['counting']} counting over included records; "
        f"at least {params['min_productivity_levels']} productivity levels; "
        f"K-S at the {params['significance_level']} level, critical value {params['ks_coefficient']}/sqrt(N), "
        f"used only above {params['ks_min_authors'] - 1} authors",
        f"  Authors: {lotka['total_authors']} across {lotka['productivity_levels']} productivity levels",
    ]
    if lotka["distribution"]:
        levels = ", ".join(f"{level['papers']}: {level['authors']}" for level in lotka["distribution"])
        lines.append(f"  Distribution (papers: authors): {levels}")
    fit = lotka["fit"]
    if fit is None:
        lines.extend([f"  Fit: not computed. {lotka['reason']}", ""])
        return lines
    lines.append(f"  Fit: alpha = {fit['alpha']}, C = {fit['C']}, R^2 = {fit['r_squared']}")
    gof = fit["goodness_of_fit"]
    if gof["D"] is None:
        lines.append(f"  Kolmogorov-Smirnov: not computed. {gof['reason']}")
    elif gof["critical_value"] is None:
        lines.append(f"  Kolmogorov-Smirnov: D = {gof['D']}, no verdict. {gof['reason']}")
    else:
        lines.append(
            f"  Kolmogorov-Smirnov: D = {gof['D']}, critical value = {gof['critical_value']} "
            f"at the {gof['significance_level']} level; "
            f"consistent with Lotka's law: {_yes_no(gof['consistent_with_lotka'])}"
        )
    lines.append("")
    return lines


def generate_screening_decisions_csv(decisions: tuple[ScreeningDecision, ...] | list[ScreeningDecision]) -> str:
    """Per-decision screening log, one row per ``ScreeningDecision`` in log order."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_SCREENING_DECISION_CSV_HEADER)
    for d in decisions:
        pub = d.publication
        writer.writerow([
            d.id,
            _utc_stamp(d.decided_at, timespec="microseconds"),
            _csv_safe(d.reviewer or ""),
            d.source,
            d.run_id or "",
            _decision_action(d),
            _criteria_json(d.criteria),
            d.publication_id,
            _csv_safe(pub.pmid or "") if pub else "",
            _csv_safe(pub.doi or "") if pub else "",
            "true" if d.previous_excluded else "false",
            _csv_safe(d.previous_exclusion_reason or ""),
            d.previous_screening_stage or "",
            "true" if d.excluded else "false",
            _csv_safe(d.exclusion_reason or ""),
            d.screening_stage or "",
        ])
    return output.getvalue()


def _split_bulk_exclude_steps(steps: list[MethodologyStep]) -> tuple[list[MethodologyStep], list[MethodologyStep]]:
    """Separate project-wide bulk-exclusion steps from the per-query pipeline.
    They are filed under one query, so letting them into the pipeline would make
    one a query's terminal step and skew the included and PRISMA totals."""
    pipeline = [s for s in steps if s.phase != BULK_EXCLUDE_PHASE]
    bulk = [s for s in steps if s.phase == BULK_EXCLUDE_PHASE]
    return pipeline, bulk


def generate_methodology(
    project_name: str,
    steps: list[MethodologyStep],
    exclusion_summary: ExclusionSummary | None = None,
    decision_log: ScreeningDecisionLog | None = None,
    author_productivity: dict | None = None,
) -> str:
    lines = [
        f'METHODOLOGY LOG — Project: "{project_name}"',
        f"Generated: {date.today().isoformat()}",
        "Tool: BibMedEd (https://github.com/ata381/bibmeded)",
        "",
    ]
    pipeline_steps, bulk_steps = _split_bulk_exclude_steps(steps)
    history_log = decision_log or ScreeningDecisionLog(decisions=())
    if not pipeline_steps:
        lines.append("No methodology steps recorded for this project.")
        if bulk_steps or history_log.decisions or history_log.unlogged_exclusions:
            lines.append("")
            lines.extend(_screening_decision_lines(history_log, bulk_steps))
        return "\n".join(lines)

    current_phase = None
    for step in pipeline_steps:
        phase_header = _PHASE_LABELS.get(step.phase, step.phase.upper())
        if phase_header != current_phase:
            current_phase = phase_header
            lines.append(current_phase)
        lines.append(f"  Step {step.step_order}: {step.action}")
        if step.phase == "search":
            query_str = step.parameters.get("query", "")
            if query_str:
                lines.append(f"    Query: {query_str}")
            searched_at = step.parameters.get("searched_at")
            if searched_at:
                lines.append(f"    Searched at: {searched_at}")
            rate_limit = step.parameters.get("rate_limit_per_second")
            if rate_limit:
                lines.append(f"    Request rate limit: {rate_limit:g} requests/s")
            capped = step.parameters.get("capped", False)
            max_results = step.parameters.get("max_results")
            if capped and max_results:
                lines.append(
                    f"    Results: {step.records_out} records (capped at max_results={max_results}; "
                    f"full set not retrieved)"
                )
            else:
                lines.append(f"    Results: {step.records_out} records")
        elif step.phase == "fetch":
            lines.append(
                f"    Retrieved: {step.records_out} of {step.records_in} "
                f"({step.records_affected} unavailable)"
            )
            persist_failures = step.parameters.get("persist_failures") or []
            persist_failed = max(step.parameters.get("persist_failed") or 0, len(persist_failures))
            if persist_failed:
                lines.append(f"    Failed to persist: {persist_failed} record(s)")
                for failure in persist_failures:
                    lines.append(
                        f"      - {failure.get('source_id')} "
                        f"({failure.get('source_database')}): {failure.get('error')}"
                    )
                omitted = persist_failed - len(persist_failures)
                if omitted:
                    lines.append(f"      ... {omitted} more not listed")
        elif step.phase == "dedup":
            method = step.parameters.get("method", "unknown")
            fields = step.parameters.get("fields") or step.parameters.get("field") or ""
            if fields:
                lines.append(f"    Method: {method} on {fields}")
            else:
                lines.append(f"    Method: {method}")
            removed_by = step.parameters.get("removed_by")
            if isinstance(removed_by, dict) and removed_by:
                breakdown = ", ".join(f"{k}={v}" for k, v in removed_by.items() if v)
                if breakdown:
                    lines.append(f"    Removed by field: {breakdown}")
            lines.append(
                f"    Removed: {step.records_affected} duplicates "
                f"({step.records_in} → {step.records_out})"
            )
        elif step.phase == "enrichment":
            source_name = step.parameters.get("source", "")
            enriched = step.parameters.get("enriched", 0)
            missing = step.parameters.get("missing", 0)
            lines.append(f"    Source: {source_name}")
            lines.append(
                f"    Enriched: {enriched} of {step.records_in} records ({missing} not found)"
            )
        elif step.phase == "exclusion":
            lines.append(
                f"    Excluded: {step.records_affected} records "
                f"({step.records_in} → {step.records_out})"
            )
        lines.append("")

    lines.extend(_screening_stage_lines(exclusion_summary))
    if decision_log is not None or bulk_steps:
        lines.extend(_screening_decision_lines(history_log, bulk_steps))

    # For a multi-query project, `steps` interleaves the per-query pipelines
    # (ordered query_id, step_order), so steps[-1] is only the *last query's*
    # terminal step — not the project-wide total. Take each query's own
    # terminal step (the last one seen for that query_id) and sum their
    # records_out to get the true project-wide included-studies figure.
    terminal_step_by_query: dict[int, MethodologyStep] = {}
    for step in pipeline_steps:
        terminal_step_by_query[step.query_id] = step
    studies_included = sum(step.records_out for step in terminal_step_by_query.values())

    lines.append("FINAL DATASET")
    lines.append(f"  Studies included: {studies_included}")
    lines.append("")
    if author_productivity is not None:
        lines.extend(_lotka_lines(author_productivity))
    return "\n".join(lines)


def generate_prisma_svg(
    project_name: str,
    steps: list[MethodologyStep],
    exclusion_summary: ExclusionSummary | None = None,
    included_count: int | None = None,
) -> str:
    pipeline_steps, _ = _split_bulk_exclude_steps(steps)
    counts = compute_counts(pipeline_steps, exclusion_summary=exclusion_summary, included_override=included_count)
    return render_svg(counts, project_name)


def generate_bundle(
    project_name: str,
    pubs: list[Publication],
    steps: list[MethodologyStep],
    exclusion_summary: ExclusionSummary | None = None,
    decision_log: ScreeningDecisionLog | None = None,
    author_productivity: dict | None = None,
) -> bytes:
    """Produce a single .zip containing CSV, RIS, WoS plain text, JSON, methodology .txt, PRISMA .svg,
    the screening decision log CSV (when ``decision_log`` is given), and a manifest."""
    stamp = date.today().isoformat()
    slug = slugify(project_name) or "project"
    # pubs is already filtered to excluded == False by the caller (_get_project_and_pubs),
    # so len(pubs) is the authoritative "included" count.
    included_count = len(pubs)
    decisions_name = f"{slug}-screening-decisions-{stamp}.csv"
    cited_written, cited_reported = wos_reference_coverage(pubs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}-{stamp}.csv", generate_csv(pubs))
        zf.writestr(f"{slug}-{stamp}.ris", generate_ris(pubs))
        zf.writestr(f"{slug}-wos-{stamp}.txt", generate_wos_plaintext(pubs))
        zf.writestr(f"{slug}-{stamp}.json", generate_json(project_name, pubs))
        zf.writestr(
            f"{slug}-methodology-{stamp}.txt",
            generate_methodology(project_name, steps, exclusion_summary, decision_log, author_productivity),
        )
        zf.writestr(f"{slug}-prisma-{stamp}.svg", generate_prisma_svg(project_name, steps, exclusion_summary, included_count=included_count))
        if decision_log is not None:
            zf.writestr(decisions_name, generate_screening_decisions_csv(decision_log.decisions))
        manifest = (
            f"BibMedEd export bundle\n"
            f"Project: {project_name}\n"
            f"Generated: {stamp}\n"
            f"Schema version: {EXPORT_SCHEMA_VERSION}\n"
            f"Included files:\n"
            f"  - {slug}-{stamp}.csv ({len(pubs)} records)\n"
            f"  - {slug}-{stamp}.ris ({len(pubs)} records)\n"
            f"  - {slug}-wos-{stamp}.txt ({len(pubs)} records, Web of Science plain text; "
            f"CR lists {cited_written} of {cited_reported} cited references, "
            f"only those with a DOI or matching an in-corpus record with a DOI)\n"
            f"  - {slug}-{stamp}.json ({len(pubs)} records, schema_version={EXPORT_SCHEMA_VERSION})\n"
            f"  - {slug}-methodology-{stamp}.txt ({len(steps)} steps)\n"
            f"  - {slug}-prisma-{stamp}.svg\n"
        )
        if decision_log is not None:
            manifest += f"  - {decisions_name} ({_plural(len(decision_log.decisions), 'decision')})\n"
        zf.writestr("MANIFEST.txt", manifest)
    return buf.getvalue()
