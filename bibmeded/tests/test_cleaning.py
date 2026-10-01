import pytest
from bibmeded.services.cleaning import normalize_name, deduplicate_records, extract_country
from bibmeded.services.pubmed import PubMedRecord

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


from bibmeded.adapters.base import RawRecord
from bibmeded.services.cleaning import deduplicate_cross_source


def test_cross_source_dedup_by_doi():
    records = [
        RawRecord(source_id="PM1", source_database="pubmed", title="Paper A", external_ids={"pmid": "PM1", "doi": "10.1/a"}),
        RawRecord(source_id="OA1", source_database="openalex", title="Paper A", external_ids={"openalex": "OA1", "doi": "10.1/a"}),
    ]
    unique, removed, breakdown = deduplicate_cross_source(records)
    assert len(unique) == 1
    assert removed == 1
    assert breakdown["doi"] == 1
    assert unique[0].source_database == "pubmed"


def test_cross_source_dedup_by_pmid():
    records = [
        RawRecord(source_id="PM1", source_database="pubmed", title="Paper A", external_ids={"pmid": "PM1"}),
        RawRecord(source_id="OA1", source_database="openalex", title="Paper A", external_ids={"openalex": "OA1", "pmid": "PM1"}),
    ]
    unique, removed, breakdown = deduplicate_cross_source(records)
    assert len(unique) == 1
    assert removed == 1
    assert breakdown["pmid"] == 1


def test_cross_source_dedup_no_overlap():
    records = [
        RawRecord(source_id="PM1", source_database="pubmed", title="Paper A", external_ids={"pmid": "PM1", "doi": "10.1/a"}),
        RawRecord(source_id="OA1", source_database="openalex", title="Paper B", external_ids={"openalex": "OA1", "doi": "10.1/b"}),
    ]
    unique, removed, breakdown = deduplicate_cross_source(records)
    assert len(unique) == 2
    assert removed == 0


def test_cross_source_dedup_uses_doi_field_fallback():
    records = [
        RawRecord(source_id="PM1", source_database="pubmed", title="A", doi="10.1/a", external_ids={"pmid": "PM1"}),
        RawRecord(source_id="OA1", source_database="openalex", title="A", doi="10.1/a", external_ids={"openalex": "OA1"}),
    ]
    unique, removed, breakdown = deduplicate_cross_source(records)
    assert len(unique) == 1
    assert breakdown["doi"] == 1


def test_cross_source_dedup_empty():
    unique, removed, breakdown = deduplicate_cross_source([])
    assert unique == []
    assert removed == 0


def test_cross_source_dedup_normalizes_doi_case_and_url_prefix():
    records = [
        RawRecord(source_id="PM1", source_database="pubmed", title="A", external_ids={"pmid": "PM1", "doi": "10.1000/ABC"}),
        RawRecord(source_id="OA1", source_database="openalex", title="A", external_ids={"openalex": "OA1", "doi": "https://doi.org/10.1000/abc"}),
    ]
    unique, removed, breakdown = deduplicate_cross_source(records)
    assert len(unique) == 1
    assert removed == 1
    assert breakdown["doi"] == 1


def test_cross_source_dedup_normalizes_pmid_whitespace():
    records = [
        RawRecord(source_id="PM1", source_database="pubmed", title="A", external_ids={"pmid": " 12345 "}),
        RawRecord(source_id="OA1", source_database="openalex", title="A", external_ids={"openalex": "OA1", "pmid": "12345"}),
    ]
    unique, removed, breakdown = deduplicate_cross_source(records)
    assert len(unique) == 1
    assert removed == 1
    assert breakdown["pmid"] == 1


def test_extract_country_is_case_insensitive_for_canonical_country_names():
    assert extract_country("Department of Surgery, toronto, canada") == "Canada"


def test_cross_source_dedup_chains_through_dropped_records_other_identifier():
    records = [
        RawRecord(source_id="PM1", source_database="pubmed", title="A", external_ids={"pmid": "100"}),
        RawRecord(source_id="PM2", source_database="pubmed", title="A", external_ids={"pmid": "100", "doi": "10.1/x"}),
        RawRecord(source_id="OA1", source_database="openalex", title="A", external_ids={"openalex": "OA1", "doi": "10.1/x"}),
    ]
    unique, removed, breakdown = deduplicate_cross_source(records)
    assert len(unique) == 1
    assert removed == 2
    assert breakdown["pmid"] + breakdown["doi"] == 2


@pytest.mark.parametrize(
    "affiliation, expected_country",
    [
        (
            "Dept of Surgery, Harvard Medical School, Boston, MA 02115, USA. jdoe@hms.harvard.edu",
            "USA",
        ),
        (
            "Division of Cardiology, University of Ottawa Heart Institute, Ottawa, Canada. Electronic address: doc@ottawaheart.ca.",
            "Canada",
        ),
        (
            "Department of Medicine, Imperial College London, London, UK <m.smith@imperial.ac.uk>",
            "UK",
        ),
        (
            "Department of Oncology, University of Turin, Turin, Italy (oncology@unito.it)",
            "Italy",
        ),
        (
            "Nuffield Department of Clinical Neurosciences, University of Oxford, Oxford, UK OX1 2JD",
            "UK",
        ),
        (
            "UCL Institute of Child Health, London, UK WC1E 6BT",
            "UK",
        ),
        (
            "Sorbonne Université, INSERM, Paris, France 75005",
            "France",
        ),
        (
            "Charité - Universitätsmedizin Berlin, Berlin, Germany D-10117",
            "Germany",
        ),
        (
            "Ege University Faculty of Medicine, Bornova, Izmir, Turkey 35100",
            "Turkey",
        ),
        (
            "Universidade de São Paulo, São Paulo, Brazil 01246-903",
            "Brazil",
        ),
        (
            "Dalla Lana School of Public Health, University of Toronto, Toronto, ON, Canada M5S 2Z9",
            "Canada",
        ),
        (
            "Johns Hopkins University School of Medicine, Baltimore, Maryland",
            "USA",
        ),
        (
            "University of Washington School of Medicine, Seattle, WA",
            "USA",
        ),
        (
            "Massachusetts General Hospital, Boston, MA 02114",
            "USA",
        ),
        (
            "Perelman School of Medicine, University of Pennsylvania, Philadelphia, PA 19104-6056",
            "USA",
        ),
        (
            "Mayo Clinic Alix School of Medicine, Rochester, Minnesota. researcher@mayo.edu",
            "USA",
        ),
        (
            "Seoul National University College of Medicine, Seoul, Republic of Korea",
            "South Korea",
        ),
        (
            "Yonsei University College of Medicine, Seoul, South Korea",
            "South Korea",
        ),
        (
            "Istanbul University, Istanbul Faculty of Medicine, Istanbul, Türkiye",
            "Turkey",
        ),
        (
            "Hacettepe University Faculty of Medicine, Ankara, Turkiye",
            "Turkey",
        ),
        (
            "Hanoi Medical University, Hanoi, Viet Nam",
            "Vietnam",
        ),
        (
            "Sechenov First Moscow State Medical University, Moscow, Russian Federation",
            "Russia",
        ),
        (
            "Fudan University Shanghai Cancer Center, Shanghai, P.R. China",
            "China",
        ),
        (
            "University of Edinburgh Medical School, Edinburgh, Scotland",
            "UK",
        ),
        (
            "Department of Biochemistry, University of Cambridge, Cambridge, UK CB2 1QW. info@bioc.cam.ac.uk",
            "UK",
        ),
        (
            "Unknown Research Institute, Global Lab",
            None,
        ),
    ],
)
def test_extract_country_real_world_affiliations(affiliation, expected_country):
    assert extract_country(affiliation) == expected_country

