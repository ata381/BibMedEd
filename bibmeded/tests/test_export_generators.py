"""Unit tests for app.services.export_generators.

These build Publication / Author / Journal / Keyword / MethodologyStep instances
purely in-memory (no DB session) since the generator functions only read
attributes/relationships that are already populated in memory.
"""

import csv
import io
import json
import zipfile
from datetime import datetime, timezone

import pytest

from app.models.author import Author
from app.models.journal import Journal
from app.models.keyword import Keyword, KeywordType
from app.models.methodology import MethodologyStep
from app.models.publication import Publication
from app.services.export_generators import (
    EXPORT_SCHEMA_VERSION,
    generate_bundle,
    generate_csv,
    generate_json,
    generate_methodology,
    generate_ris,
)


def make_pub(
    *,
    pmid="12345",
    doi="10.1000/xyz",
    title="A Study of Things",
    abstract="An abstract.",
    year=2020,
    citation_count=5,
    authors=None,
    journal_name="Journal of Testing",
    keywords=None,
    publication_type="Journal Article",
    source_database="pubmed",
    excluded=False,
    exclusion_reason=None,
):
    pub = Publication(
        pmid=pmid,
        doi=doi,
        title=title,
        abstract=abstract,
        year=year,
        citation_count=citation_count,
        publication_type=publication_type,
        source_database=source_database,
        excluded=excluded,
        exclusion_reason=exclusion_reason,
    )
    pub.authors = authors if authors is not None else [Author(name="Doe J")]
    pub.journal = Journal(name=journal_name) if journal_name is not None else None
    pub.keywords = (
        keywords
        if keywords is not None
        else [Keyword(term="medical education", type=KeywordType.author_keyword)]
    )
    return pub


def make_step(
    *,
    query_id=1,
    step_order=1,
    phase="search",
    source="pubmed",
    action="Search",
    records_in=0,
    records_out=10,
    records_affected=10,
    parameters=None,
):
    return MethodologyStep(
        query_id=query_id,
        step_order=step_order,
        phase=phase,
        source=source,
        action=action,
        records_in=records_in,
        records_out=records_out,
        records_affected=records_affected,
        parameters=parameters or {},
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# generate_csv
# ---------------------------------------------------------------------------


class TestGenerateCsv:
    def test_writes_header_row(self):
        csv_text = generate_csv([])
        rows = list(csv.reader(io.StringIO(csv_text)))
        assert rows == [
            ["PMID", "DOI", "Title", "Authors", "Journal", "Year", "Citations", "Keywords", "Abstract"]
        ]

    def test_writes_exact_row_content_for_a_publication(self):
        pub = make_pub(
            pmid="999",
            doi="10.1/abc",
            title="Effects of Simulation Training",
            abstract="Line one.\nLine two.",
            year=2021,
            citation_count=42,
            authors=[Author(name="Smith A"), Author(name="Jones B")],
            journal_name="Medical Education Review",
            keywords=[
                Keyword(term="simulation", type=KeywordType.author_keyword),
                Keyword(term="training", type=KeywordType.author_keyword),
            ],
        )
        csv_text = generate_csv([pub])
        rows = list(csv.reader(io.StringIO(csv_text)))
        assert len(rows) == 2
        data_row = rows[1]
        assert data_row[0] == "999"
        assert data_row[1] == "10.1/abc"
        assert data_row[2] == "Effects of Simulation Training"
        assert data_row[3] == "Smith A; Jones B"
        assert data_row[4] == "Medical Education Review"
        assert data_row[5] == "2021"
        assert data_row[6] == "42"
        assert data_row[7] == "simulation; training"
        # Newlines inside the abstract are flattened to spaces.
        assert data_row[8] == "Line one. Line two."

    def test_handles_missing_optional_fields(self):
        pub = make_pub(doi=None, journal_name=None, keywords=[], authors=[], abstract=None, year=None)
        csv_text = generate_csv([pub])
        rows = list(csv.reader(io.StringIO(csv_text)))
        data_row = rows[1]
        assert data_row[1] == ""  # doi
        assert data_row[3] == ""  # authors
        assert data_row[4] == ""  # journal
        assert data_row[5] == ""  # year
        assert data_row[7] == ""  # keywords
        assert data_row[8] == ""  # abstract

    @pytest.mark.parametrize("trigger", ["=", "+", "-", "@", "\t", "\r"])
    def test_escapes_formula_injection_in_title(self, trigger):
        """OWASP CSV injection: a cell starting with =, +, -, @ (or tab/CR) can be
        interpreted as a formula by Excel/Sheets. Such values must be prefixed
        with a leading apostrophe so they are treated as plain text.
        """
        malicious_title = f"{trigger}cmd|'/c calc'!A1"
        pub = make_pub(title=malicious_title)
        csv_text = generate_csv([pub])
        rows = list(csv.reader(io.StringIO(csv_text)))
        data_row = rows[1]
        assert data_row[2] == "'" + malicious_title
        assert not data_row[2].startswith(trigger)

    def test_escapes_formula_injection_in_authors_and_journal_and_keywords(self):
        pub = make_pub(
            title="Safe Title",
            authors=[Author(name="=HYPERLINK(\"http://evil\")")],
            journal_name="+1+1",
            keywords=[Keyword(term="@evil", type=KeywordType.author_keyword)],
        )
        csv_text = generate_csv([pub])
        rows = list(csv.reader(io.StringIO(csv_text)))
        data_row = rows[1]
        assert data_row[3].startswith("'=")
        assert data_row[4].startswith("'+")
        assert data_row[7].startswith("'@")

    def test_does_not_escape_benign_values(self):
        pub = make_pub(title="Benign Title", journal_name="Regular Journal")
        csv_text = generate_csv([pub])
        rows = list(csv.reader(io.StringIO(csv_text)))
        data_row = rows[1]
        assert data_row[2] == "Benign Title"
        assert data_row[4] == "Regular Journal"


# ---------------------------------------------------------------------------
# generate_json
# ---------------------------------------------------------------------------


class TestGenerateJson:
    def test_top_level_schema_shape(self):
        pub = make_pub()
        json_text = generate_json("My Project", [pub])
        payload = json.loads(json_text)
        assert payload["schema_version"] == EXPORT_SCHEMA_VERSION
        assert payload["project"] == "My Project"
        assert payload["count"] == 1
        assert "generated" in payload
        assert isinstance(payload["publications"], list)
        assert len(payload["publications"]) == 1

    def test_publication_entry_shape(self):
        pub = make_pub(
            pmid="42",
            doi="10.1/x",
            title="Title",
            abstract="Abstract text",
            year=2019,
            publication_type="Review",
            source_database="crossref",
            citation_count=7,
            authors=[Author(name="Alice", orcid="0000-0001")],
            journal_name="Journal X",
            keywords=[Keyword(term="kw1", type=KeywordType.mesh_term)],
        )
        payload = json.loads(generate_json("Proj", [pub]))
        entry = payload["publications"][0]
        assert entry["pmid"] == "42"
        assert entry["doi"] == "10.1/x"
        assert entry["title"] == "Title"
        assert entry["abstract"] == "Abstract text"
        assert entry["year"] == 2019
        assert entry["publication_type"] == "Review"
        assert entry["source_database"] == "crossref"
        assert entry["citation_count"] == 7
        assert entry["excluded"] is False
        assert entry["exclusion_reason"] is None
        assert entry["journal_name"] == "Journal X"
        assert entry["authors"] == [{"name": "Alice", "orcid": "0000-0001"}]
        assert entry["keywords"] == ["kw1"]

    def test_empty_publication_list(self):
        payload = json.loads(generate_json("Empty Project", []))
        assert payload["count"] == 0
        assert payload["publications"] == []

    def test_round_trips_non_ascii_characters(self):
        pub = make_pub(title="Tıp Eğitiminde Yapay Zekâ – 教育")
        json_text = generate_json("Proj", [pub])
        # ensure_ascii=False means non-ASCII chars are written literally, not \uXXXX escaped
        assert "Tıp Eğitiminde Yapay Zekâ" in json_text
        payload = json.loads(json_text)
        assert payload["publications"][0]["title"] == "Tıp Eğitiminde Yapay Zekâ – 教育"


# ---------------------------------------------------------------------------
# generate_ris
# ---------------------------------------------------------------------------


class TestGenerateRis:
    def test_writes_expected_tag_sequence(self):
        pub = make_pub(
            pmid="55",
            doi="10.1/z",
            title="RIS Title",
            year=2018,
            authors=[Author(name="Author One"), Author(name="Author Two")],
            journal_name="RIS Journal",
            keywords=[Keyword(term="kw-a", type=KeywordType.author_keyword)],
            abstract="Some abstract",
        )
        ris_text = generate_ris([pub])
        lines = ris_text.split("\n")
        assert lines[0] == "TY  - JOUR"
        assert lines[1] == "TI  - RIS Title"
        assert lines[2] == "AU  - Author One"
        assert lines[3] == "AU  - Author Two"
        assert lines[4] == "JO  - RIS Journal"
        assert lines[5] == "PY  - 2018"
        assert lines[6] == "DO  - 10.1/z"
        assert lines[7] == "AN  - 55"
        assert lines[8] == "AB  - Some abstract"
        assert lines[9] == "KW  - kw-a"
        assert lines[10] == "ER  - "

    def test_omits_optional_tags_when_absent(self):
        pub = make_pub(doi=None, journal_name=None, keywords=[], abstract=None, authors=[])
        ris_text = generate_ris([pub])
        assert "JO  - " not in ris_text
        assert "DO  - " not in ris_text
        assert "AB  - " not in ris_text
        assert "KW  - " not in ris_text
        assert "AU  - " not in ris_text

    def test_multiple_publications_each_terminated(self):
        pubs = [make_pub(pmid="1"), make_pub(pmid="2")]
        ris_text = generate_ris(pubs)
        er_lines = [line for line in ris_text.split("\n") if line == "ER  - "]
        assert len(er_lines) == 2

    def test_sanitizes_newline_injection_in_title(self):
        """A malicious record with a newline + fake 'ER  - ' + 'TY  - JOUR' in the
        title must not be able to inject an extra RIS record boundary.
        """
        malicious_title = "Normal Title\nER  - \nTY  - JOUR\nAB  - injected record"
        pub = make_pub(pmid="66", title=malicious_title)
        ris_text = generate_ris([pub])
        lines = ris_text.split("\n")
        # Exactly one legitimate ER line for this single record.
        er_lines = [line for line in lines if line == "ER  - "]
        assert len(er_lines) == 1
        # No injected TY line should appear beyond the legitimate first one.
        ty_lines = [line for line in lines if line == "TY  - JOUR"]
        assert len(ty_lines) == 1
        # The title tag itself must not contain a raw newline.
        title_lines = [line for line in lines if line.startswith("TI  - ")]
        assert len(title_lines) == 1
        assert "\n" not in title_lines[0]

    def test_sanitizes_newline_injection_in_author_and_journal_and_keyword(self):
        pub = make_pub(
            title="Safe",
            authors=[Author(name="Evil\nER  - \nTY  - JOUR")],
            journal_name="Journal\nER  - ",
            keywords=[Keyword(term="kw\nER  - ", type=KeywordType.author_keyword)],
        )
        ris_text = generate_ris([pub])
        er_lines = [line for line in ris_text.split("\n") if line == "ER  - "]
        assert len(er_lines) == 1


# ---------------------------------------------------------------------------
# generate_bundle
# ---------------------------------------------------------------------------


class TestGenerateBundle:
    def test_zip_contains_all_expected_members(self):
        pub = make_pub()
        steps = [make_step(query_id=1, step_order=1, phase="search", records_out=10)]
        bundle_bytes = generate_bundle("Bundle Project", [pub], steps, {})
        zf = zipfile.ZipFile(io.BytesIO(bundle_bytes))
        names = zf.namelist()
        assert any(name.endswith(".csv") for name in names)
        assert any(name.endswith(".ris") for name in names)
        assert any(name.endswith(".json") for name in names)
        assert any("methodology" in name and name.endswith(".txt") for name in names)
        assert any(name.endswith(".svg") for name in names)
        assert "MANIFEST.txt" in names

    def test_manifest_mentions_schema_version_and_counts(self):
        pubs = [make_pub(pmid="1"), make_pub(pmid="2")]
        steps = [make_step(records_out=2)]
        bundle_bytes = generate_bundle("Bundle Project", pubs, steps, {})
        zf = zipfile.ZipFile(io.BytesIO(bundle_bytes))
        manifest = zf.read("MANIFEST.txt").decode("utf-8")
        assert EXPORT_SCHEMA_VERSION in manifest
        assert "2 records" in manifest
        assert "Bundle Project" in manifest


# ---------------------------------------------------------------------------
# generate_methodology — multi-query "Studies included" total (finding [12])
# ---------------------------------------------------------------------------


class TestGenerateMethodologyStudiesIncluded:
    def test_single_query_uses_last_step_records_out(self):
        steps = [
            make_step(query_id=1, step_order=1, phase="search", records_in=0, records_out=100, records_affected=100),
            make_step(query_id=1, step_order=2, phase="fetch", records_in=100, records_out=95, records_affected=5),
        ]
        text = generate_methodology("Single Query Project", steps)
        assert "Studies included: 95" in text

    def test_multi_query_totals_across_queries_not_just_last_query(self):
        """Two queries in one project, each contributing separately-tracked
        included studies. The final "Studies included" figure must be the sum
        across both queries, not just the last query's last step.
        """
        steps = [
            # Query 1: ends with 60 included studies.
            make_step(query_id=1, step_order=1, phase="search", records_in=0, records_out=200, records_affected=200),
            make_step(query_id=1, step_order=2, phase="fetch", records_in=200, records_out=60, records_affected=140),
            # Query 2: ends with 30 included studies.
            make_step(query_id=2, step_order=1, phase="search", records_in=0, records_out=50, records_affected=50),
            make_step(query_id=2, step_order=2, phase="fetch", records_in=50, records_out=30, records_affected=20),
        ]
        text = generate_methodology("Multi Query Project", steps)
        # Old buggy behavior would report only steps[-1].records_out == 30.
        assert "Studies included: 90" in text
        assert "Studies included: 30" not in text

    def test_no_steps_returns_placeholder_and_no_studies_line(self):
        text = generate_methodology("Empty Project", [])
        assert "No methodology steps recorded" in text
        assert "Studies included" not in text
