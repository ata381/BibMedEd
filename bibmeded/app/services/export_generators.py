"""Pure-function generators for the export endpoints.

Each function returns its full content as text/bytes so callers (router endpoints, the
bundle endpoint, tests) can compose them without going through Starlette `StreamingResponse`.
"""

import csv
import io
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


def generate_methodology(project_name: str, steps: list[MethodologyStep]) -> str:
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

    last_step = steps[-1]
    lines.append("FINAL DATASET")
    lines.append(f"  Studies included: {last_step.records_out}")
    lines.append("")
    return "\n".join(lines)


def generate_prisma_svg(project_name: str, steps: list[MethodologyStep]) -> str:
    counts = compute_counts(steps)
    return render_svg(counts, project_name)


def generate_bundle(
    project_name: str, pubs: list[Publication], steps: list[MethodologyStep]
) -> bytes:
    """Produce a single .zip containing CSV, RIS, methodology .txt, PRISMA .svg, and a manifest."""
    stamp = date.today().isoformat()
    slug = slugify(project_name) or "project"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}-{stamp}.csv", generate_csv(pubs))
        zf.writestr(f"{slug}-{stamp}.ris", generate_ris(pubs))
        zf.writestr(f"{slug}-methodology-{stamp}.txt", generate_methodology(project_name, steps))
        zf.writestr(f"{slug}-prisma-{stamp}.svg", generate_prisma_svg(project_name, steps))
        manifest = (
            f"BibMedEd export bundle\n"
            f"Project: {project_name}\n"
            f"Generated: {stamp}\n"
            f"Included files:\n"
            f"  - {slug}-{stamp}.csv ({len(pubs)} records)\n"
            f"  - {slug}-{stamp}.ris ({len(pubs)} records)\n"
            f"  - {slug}-methodology-{stamp}.txt ({len(steps)} steps)\n"
            f"  - {slug}-prisma-{stamp}.svg\n"
        )
        zf.writestr("MANIFEST.txt", manifest)
    return buf.getvalue()
