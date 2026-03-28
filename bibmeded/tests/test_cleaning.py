from app.services.cleaning import normalize_name, deduplicate_records, extract_country
from app.services.pubmed import PubMedRecord

def test_normalize_name():
    assert normalize_name("Smith, John A.") == "smith john a"
    assert normalize_name("  Chen,  Li  ") == "chen li"
    assert normalize_name("O'Brien, Mary") == "obrien mary"

def test_extract_country():
    assert extract_country("Department of Medicine, Harvard Medical School, Boston, MA, USA") == "USA"
    assert extract_country("Peking University, Beijing, China") == "China"
    assert extract_country("Unknown Affiliation") is None

def test_deduplicate_by_pmid():
    records = [
        PubMedRecord(pmid="111", title="First"),
        PubMedRecord(pmid="222", title="Second"),
        PubMedRecord(pmid="111", title="First Duplicate"),
    ]
    deduped = deduplicate_records(records)
    assert len(deduped) == 2
    assert {r.pmid for r in deduped} == {"111", "222"}
