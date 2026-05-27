"""Pure-function generators for the export endpoints.

Each function returns its full content as text/bytes so callers (router endpoints, the
bundle endpoint, tests) can compose them without going through Starlette `StreamingResponse`.
"""

import csv
import io
import json
import re
import zipfile
from datetime import date

from app.models import Publication
from app.models.methodology import MethodologyStep
from app.services.prisma import compute_counts, render_svg


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


def generate_csv(pubs: list[Publication]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["PMID", "DOI", "Title", "Authors", "Journal", "Year", "Citations", "Keywords", "Abstract"])
    for pub in pubs:
        writer.writerow([
            pub.pmid,
            pub.doi or "",
            pub.title,
            "; ".join(a.name for a in pub.authors),
            pub.journal.name if pub.journal else "",
            pub.year or "",
            pub.citation_count or 0,
            "; ".join(k.term for k in pub.keywords),
            (pub.abstract or "").replace("\n", " "),
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
        "journal_name": pub.journal.name if pub.journal else None,
        "journal_issn": pub.journal.issn if pub.journal else None,
        "authors": [
            {"name": a.name, "orcid": a.orcid}
            for a in pub.authors
        ],
        "keywords": [k.term for k in pub.keywords],
    }


def generate_json(project_name: str, pubs: list[Publication]) -> str:
    """JSON-lines-friendly bulk export. Stable schema for downstream pipelines."""
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "project": project_name,
        "generated": date.today().isoformat(),
        "count": len(pubs),
        "publications": [_publication_to_dict(p) for p in pubs],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def generate_ris(pubs: list[Publication]) -> str:
    lines: list[str] = []
    for pub in pubs:
        lines.append("TY  - JOUR")
        lines.append(f"TI  - {pub.title}")
        for author in pub.authors:
            lines.append(f"AU  - {author.name}")
        if pub.journal:
            lines.append(f"JO  - {pub.journal.name}")
        if pub.year:
            lines.append(f"PY  - {pub.year}")
        if pub.doi:
            lines.append(f"DO  - {pub.doi}")
        lines.append(f"AN  - {pub.pmid}")
        if pub.abstract:
            lines.append(f"AB  - {pub.abstract.replace(chr(10), ' ')}")
        for kw in pub.keywords:
            lines.append(f"KW  - {kw.term}")
        lines.append("ER  - ")
        lines.append("")
    return "\n".join(lines)


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


def generate_methodology(
    project_name: str,
    steps: list[MethodologyStep],
    exclusion_summary: dict[str | None, int] | None = None,
) -> str:
    lines = [
        f'METHODOLOGY LOG — Project: "{project_name}"',
        f"Generated: {date.today().isoformat()}",
        "Tool: BibMedEd (https://github.com/ata381/bibmeded)",
        "",
    ]
    if not steps:
        lines.append("No methodology steps recorded for this project.")
        return "\n".join(lines)

    current_phase = None
    for step in steps:
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

    if exclusion_summary:
        total_excluded = sum(exclusion_summary.values())
        if total_excluded > 0:
            lines.append("MANUAL EXCLUSIONS BY REASON (PRISMA 2020 item 17)")
            for reason_code, n in sorted(exclusion_summary.items(), key=lambda kv: -kv[1]):
                if n <= 0:
                    continue
                label = EXCLUSION_REASON_LABELS.get(reason_code or "other", reason_code or "Other / unspecified")
                lines.append(f"  {label}: {n}")
            lines.append("")

    last_step = steps[-1]
    lines.append("FINAL DATASET")
    lines.append(f"  Studies included: {last_step.records_out}")
    lines.append("")
    return "\n".join(lines)


def generate_prisma_svg(
    project_name: str,
    steps: list[MethodologyStep],
    exclusion_summary: dict[str | None, int] | None = None,
    included_count: int | None = None,
) -> str:
    counts = compute_counts(steps, exclusion_summary=exclusion_summary, included_override=included_count)
    return render_svg(counts, project_name)


def generate_bundle(
    project_name: str,
    pubs: list[Publication],
    steps: list[MethodologyStep],
    exclusion_summary: dict[str | None, int] | None = None,
) -> bytes:
    """Produce a single .zip containing CSV, RIS, JSON, methodology .txt, PRISMA .svg, and a manifest."""
    stamp = date.today().isoformat()
    slug = slugify(project_name) or "project"
    # pubs is already filtered to excluded == False by the caller (_get_project_and_pubs),
    # so len(pubs) is the authoritative "included" count.
    included_count = len(pubs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}-{stamp}.csv", generate_csv(pubs))
        zf.writestr(f"{slug}-{stamp}.ris", generate_ris(pubs))
        zf.writestr(f"{slug}-{stamp}.json", generate_json(project_name, pubs))
        zf.writestr(f"{slug}-methodology-{stamp}.txt", generate_methodology(project_name, steps, exclusion_summary))
        zf.writestr(f"{slug}-prisma-{stamp}.svg", generate_prisma_svg(project_name, steps, exclusion_summary, included_count=included_count))
        manifest = (
            f"BibMedEd export bundle\n"
            f"Project: {project_name}\n"
            f"Generated: {stamp}\n"
            f"Schema version: {EXPORT_SCHEMA_VERSION}\n"
            f"Included files:\n"
            f"  - {slug}-{stamp}.csv ({len(pubs)} records)\n"
            f"  - {slug}-{stamp}.ris ({len(pubs)} records)\n"
            f"  - {slug}-{stamp}.json ({len(pubs)} records, schema_version={EXPORT_SCHEMA_VERSION})\n"
            f"  - {slug}-methodology-{stamp}.txt ({len(steps)} steps)\n"
            f"  - {slug}-prisma-{stamp}.svg\n"
        )
        zf.writestr("MANIFEST.txt", manifest)
    return buf.getvalue()
