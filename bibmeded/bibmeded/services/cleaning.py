import re
from bibmeded.services.pubmed import PubMedRecord
from bibmeded.adapters.base import RawRecord as _RawRecord

COUNTRIES = [
    "USA", "United States", "China", "United Kingdom", "UK", "Germany", "Japan",
    "Canada", "Australia", "France", "Italy", "Spain", "South Korea", "India",
    "Brazil", "Netherlands", "Turkey", "Sweden", "Switzerland", "Iran",
    "Taiwan", "Saudi Arabia", "Singapore", "Belgium", "Denmark", "Norway",
    "Finland", "Austria", "Poland", "Israel", "Portugal", "Ireland",
    "New Zealand", "Greece", "Czech Republic", "Thailand", "Malaysia",
    "Mexico", "Egypt", "South Africa", "Pakistan", "Colombia", "Chile",
    "Argentina", "Indonesia", "Nigeria", "Russia", "Romania", "Hungary",
    "Vietnam",
]

COUNTRY_ALIASES = {
    "United States": "USA", "United States of America": "USA", "U.S.A.": "USA", "U.S.": "USA",
    "United Kingdom": "UK", "U.K.": "UK", "Great Britain": "UK",
    "England": "UK", "Scotland": "UK", "Wales": "UK", "Northern Ireland": "UK",
    "Republic of Korea": "South Korea", "Korea, Republic of": "South Korea",
    "Korea": "South Korea", "South Korea": "South Korea",
    "Peoples Republic of China": "China", "People's Republic of China": "China",
    "P.R. China": "China", "P. R. China": "China", "PR China": "China",
    "Türkiye": "Turkey", "Turkiye": "Turkey", "Republic of Turkey": "Turkey",
    "Viet Nam": "Vietnam", "Vietnam": "Vietnam",
    "Russian Federation": "Russia",
    "Czechia": "Czech Republic",
    "The Netherlands": "Netherlands",
}

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming", "District of Columbia",
]

US_STATE_ABBRS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

_EMAIL_RE = re.compile(
    r"[\s,;.]*(?:"
    r"\((?:electronic\s+address|e-?mail)?[:\s]*[\w.+-]+@[\w-]+\.[\w.-]+\)|"
    r"\[(?:electronic\s+address|e-?mail)?[:\s]*[\w.+-]+@[\w-]+\.[\w.-]+\]|"
    r"(?:electronic\s+address|e-?mail)?[:\s]*<?[\w.+-]+@[\w-]+\.[\w.-]+>?"
    r")\.?$",
    re.IGNORECASE,
)

_POSTCODE_RE = re.compile(
    r"[\s,;.]+(?:"
    r"[A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2}|"
    r"[A-Za-z]\d[A-Za-z]\s*\d[A-Za-z]\d|"
    r"[A-Za-z]{1,2}-\d{4,6}|"
    r"\d{4,6}(?:-\d{3,4})?|"
    r"CEDEX(?:\s*\d+)?"
    r")\.?$",
    re.IGNORECASE,
)


def _ends_with_word(text: str, suffix: str) -> bool:
    if not text.lower().endswith(suffix.lower()):
        return False
    prefix_len = len(text) - len(suffix)
    if prefix_len == 0:
        return True
    return not text[prefix_len - 1].isalnum()


def _match_country_candidate(text: str) -> str | None:
    for alias, canonical in COUNTRY_ALIASES.items():
        if _ends_with_word(text, alias):
            return canonical
    for country in COUNTRIES:
        if _ends_with_word(text, country):
            return country
    for state in US_STATES:
        if _ends_with_word(text, state):
            return "USA"
    match = re.search(r"[\s,;]+([A-Za-z]{2})\.?$", text)
    if match and match.group(1).upper() in US_STATE_ABBRS:
        return "USA"
    return None


def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def extract_country(affiliation: str) -> str | None:
    if not affiliation:
        return None
    aff = affiliation.strip().rstrip(".;,")
    aff = _EMAIL_RE.sub("", aff).strip().rstrip(".;,")
    matched = _match_country_candidate(aff)
    if matched:
        return matched

    aff_without_postcode = _POSTCODE_RE.sub("", aff).strip().rstrip(".;,")
    if aff_without_postcode != aff:
        matched = _match_country_candidate(aff_without_postcode)
        if matched:
            return matched

    return None


def _normalize_identifier(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_doi(value: str | None) -> str | None:
    normalized = _normalize_identifier(value)
    if not normalized:
        return None
    lowered = normalized.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix):]
            break
    return lowered.strip()

def deduplicate_records(records: list[PubMedRecord]) -> list[PubMedRecord]:
    seen = set()
    unique = []
    for record in records:
        if record.pmid not in seen:
            seen.add(record.pmid)
            unique.append(record)
    return unique

def deduplicate_cross_source(records: list[_RawRecord]) -> tuple[list[_RawRecord], int, dict[str, int]]:
    """Deduplicate records from multiple sources using DOI and PMID overlap.

    Returns (unique_records, total_removed, removal_breakdown_by_field).
    """
    seen_doi: set[str] = set()
    seen_pmid: set[str] = set()
    unique: list[_RawRecord] = []
    removed_by: dict[str, int] = {"doi": 0, "pmid": 0}

    for r in records:
        doi = _normalize_doi(r.external_ids.get("doi") or r.doi)
        pmid = _normalize_identifier(
            r.external_ids.get("pmid") or (r.source_id if r.source_database == "pubmed" else None)
        )

        is_duplicate = (doi and doi in seen_doi) or (pmid and pmid in seen_pmid)

        if is_duplicate:
            if doi and doi in seen_doi:
                removed_by["doi"] += 1
            else:
                removed_by["pmid"] += 1
            if doi:
                seen_doi.add(doi)
            if pmid:
                seen_pmid.add(pmid)
            continue

        if doi:
            seen_doi.add(doi)
        if pmid:
            seen_pmid.add(pmid)
        unique.append(r)

    total_removed = sum(removed_by.values())
    return unique, total_removed, removed_by
