import re
from app.services.pubmed import PubMedRecord

COUNTRIES = [
    "USA", "United States", "China", "United Kingdom", "UK", "Germany", "Japan",
    "Canada", "Australia", "France", "Italy", "Spain", "South Korea", "India",
    "Brazil", "Netherlands", "Turkey", "Sweden", "Switzerland", "Iran",
    "Taiwan", "Saudi Arabia", "Singapore", "Belgium", "Denmark", "Norway",
    "Finland", "Austria", "Poland", "Israel", "Portugal", "Ireland",
    "New Zealand", "Greece", "Czech Republic", "Thailand", "Malaysia",
    "Mexico", "Egypt", "South Africa", "Pakistan", "Colombia", "Chile",
    "Argentina", "Indonesia", "Nigeria", "Russia", "Romania", "Hungary",
]

COUNTRY_ALIASES = {
    "United States": "USA", "United States of America": "USA", "U.S.A.": "USA",
    "United Kingdom": "UK", "England": "UK", "Scotland": "UK", "Wales": "UK",
    "Republic of Korea": "South Korea", "Korea": "South Korea",
    "Peoples Republic of China": "China", "P.R. China": "China",
}

def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

def extract_country(affiliation: str) -> str | None:
    if not affiliation:
        return None
    aff = affiliation.strip().rstrip(".")
    for alias, canonical in COUNTRY_ALIASES.items():
        if aff.lower().endswith(alias.lower()):
            return canonical
    for country in COUNTRIES:
        if aff.endswith(country) or aff.endswith(country + "."):
            return country
    return None

def deduplicate_records(records: list[PubMedRecord]) -> list[PubMedRecord]:
    seen = set()
    unique = []
    for record in records:
        if record.pmid not in seen:
            seen.add(record.pmid)
            unique.append(record)
    return unique
