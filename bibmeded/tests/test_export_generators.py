"""Unit tests for bibmeded.services.export_generators.

These build Publication / Author / Journal / Keyword / MethodologyStep instances
purely in-memory (no DB session) since the generator functions only read
attributes/relationships that are already populated in memory.
"""

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone

import pytest

from bibmeded.analysis.lotka import LOTKA_METHOD, fit_lotka
from bibmeded.models.author import Affiliation, Author
from bibmeded.models.journal import Journal
from bibmeded.models.keyword import Keyword, KeywordType
from bibmeded.models.methodology import MethodologyStep
from bibmeded.models.publication import Publication
from bibmeded.models.screening import ScreeningDecision
from bibmeded.services.export_generators import (
    EXPORT_SCHEMA_VERSION,
    generate_bundle,
    generate_csv,
    generate_json,
    generate_methodology,
    generate_prisma_svg,
    generate_ris,
    generate_screening_decisions_csv,
    generate_wos_plaintext,
    wos_reference_coverage,
)
from bibmeded.services.screening import ScreeningDecisionLog


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
    screening_stage=None,
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
        screening_stage=screening_stage,
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
# generate_wos_plaintext
# ---------------------------------------------------------------------------

WOS_HEADER = ("FN Clarivate Analytics Web of Science", "VR 1.0")
_WOS_TAG_LINE = re.compile(r"^([A-Z][A-Z0-9]) (\S.*)$")
_WOS_CONTINUATION_LINE = re.compile(r"^   (\S.*)$")


def parse_wos(text: str) -> list[list[tuple[str, list[str]]]]:
    """Parse WoS tagged plain text by the published rules, failing on any deviation.

    Rules: optional UTF-8 BOM, ``FN`` then ``VR 1.0``; each record opens with ``PT``,
    every line is a two-character tag plus one space plus a value, or a 3-space
    continuation of the previous tag; ``ER`` closes a record and is followed by one
    blank line; the file ends with ``EF``.
    """
    lines = text.removeprefix("\ufeff").split("\n")
    assert tuple(lines[:2]) == WOS_HEADER
    assert lines[-2:] == ["EF", ""]
    records: list[list[tuple[str, list[str]]]] = []
    current: list[tuple[str, list[str]]] | None = None
    body = iter(lines[2:-2])
    for line in body:
        if current is None:
            assert line.startswith("PT "), f"record must open with PT, got {line!r}"
            current = []
        if line == "ER":
            assert next(body, None) == "", "ER must be followed by a blank line"
            records.append(current)
            current = None
            continue
        continuation = _WOS_CONTINUATION_LINE.match(line)
        if continuation:
            assert current, "continuation line with no open tag"
            current[-1][1].append(continuation.group(1))
            continue
        tag_line = _WOS_TAG_LINE.match(line)
        assert tag_line, f"not a WoS tag line: {line!r}"
        current.append((tag_line.group(1), [tag_line.group(2)]))
    assert current is None, "last record not closed by ER"
    return records


def wos_fields(text: str, index: int = 0) -> dict[str, list[str]]:
    return dict(parse_wos(text)[index])


def make_wos_pub(**overrides):
    defaults = dict(
        pmid="31234567",
        doi="10.1111/medu.13900",
        title="Feedback in clinical training",
        abstract="We studied feedback.",
        year=2019,
        citation_count=12,
        journal_name="Medical Education",
        source_database="pubmed",
        authors=[
            Author(
                name="Demir, Sofia Ayse",
                affiliations=[Affiliation(name="Hacettepe University, Ankara, Turkey", country="Turkey")],
            ),
            Author(
                name="Kaya, Ali",
                affiliations=[Affiliation(name="Hacettepe University, Ankara, Turkey", country="Turkey")],
            ),
            Author(
                name="Smith, John",
                affiliations=[Affiliation(name="University of Michigan, Ann Arbor, MI, USA", country="USA")],
            ),
        ],
        keywords=[
            Keyword(term="feedback", type=KeywordType.author_keyword),
            Keyword(term="simulation", type=KeywordType.author_keyword),
            Keyword(term="Education, Medical", type=KeywordType.mesh_term),
            Keyword(term="Humans", type=KeywordType.mesh_term),
        ],
    )
    external_references = overrides.pop("external_references", None)
    issn = overrides.pop("issn", "0308-0110")
    e_issn = overrides.pop("e_issn", "1365-2923")
    defaults.update(overrides)
    pub = make_pub(**defaults)
    if pub.journal is not None:
        pub.journal.issn = issn
        pub.journal.e_issn = e_issn
    pub.external_references = external_references
    return pub


class TestGenerateWosPlaintext:
    @pytest.mark.parametrize(
        "malformed",
        [
            "FN Clarivate Analytics Web of Science\nVR 1.0\nPT J\nTI \nER\n\nEF\n",
            "FN Clarivate Analytics Web of Science\nVR 1.0\nPT J\n  two-space continuation\nER\n\nEF\n",
            "FN Clarivate Analytics Web of Science\nVR 1.0\nPT J\nER\nPT J\nER\n\nEF\n",
            "FN Clarivate Analytics Web of Science\nVR 1.0\nPT J\nER\n\n",
        ],
    )
    def test_format_checker_rejects_malformed_files(self, malformed):
        with pytest.raises(AssertionError):
            parse_wos(malformed)

    def test_header_and_footer_follow_the_published_format(self):
        text = generate_wos_plaintext([make_wos_pub()])
        assert text.startswith("\ufeffFN Clarivate Analytics Web of Science\nVR 1.0\nPT J\n")
        assert text.endswith("\nER\n\nEF\n")

    def test_empty_corpus_is_a_valid_file_with_no_records(self):
        text = generate_wos_plaintext([])
        assert parse_wos(text) == []

    def test_tags_are_emitted_in_web_of_science_order(self):
        pub = make_wos_pub(
            external_references=["10.1000/cited-one"],
            publication_type="Journal Article",
        )
        tags = [tag for tag, _ in parse_wos(generate_wos_plaintext([pub]))[0]]
        assert tags == [
            "PT", "AU", "AF", "TI", "SO", "DT", "DE", "ID", "AB", "C1", "CR", "NR",
            "TC", "SN", "EI", "PY", "DI", "UT", "PM",
        ]

    def test_one_author_per_line_in_surname_initials_form(self):
        text = generate_wos_plaintext([make_wos_pub()])
        assert "\nAU Demir, SA\n   Kaya, A\n   Smith, J\n" in text
        assert wos_fields(text)["AU"] == ["Demir, SA", "Kaya, A", "Smith, J"]
        assert wos_fields(text)["AF"] == ["Demir, Sofia Ayse", "Kaya, Ali", "Smith, John"]

    def test_given_family_names_are_reordered_to_surname_first(self):
        pub = make_wos_pub(
            source_database="openalex",
            authors=[Author(name="Jean-Pierre Dupont"), Author(name="Mary J. Watson")],
        )
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert fields["AU"] == ["Dupont, JP", "Watson, MJ"]
        assert fields["AF"] == ["Dupont, Jean-Pierre", "Watson, Mary J."]

    def test_pubmed_collective_and_single_token_names_are_kept_verbatim(self):
        pub = make_wos_pub(authors=[Author(name="STARD Study Group"), Author(name="Plato")])
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert fields["AU"] == ["STARD Study Group", "Plato"]
        assert fields["AF"] == ["STARD Study Group", "Plato"]

    def test_c1_groups_authors_by_affiliation_and_keeps_the_country(self):
        fields = wos_fields(generate_wos_plaintext([make_wos_pub()]))
        assert fields["C1"] == [
            "[Demir, SA; Kaya, A] Hacettepe University, Ankara, Turkey.",
            "[Smith, J] University of Michigan, Ann Arbor, MI, USA.",
        ]

    def test_c1_address_ends_with_exactly_one_period(self):
        # bibliometrix splits the space-joined C1 lines into addresses on "." and
        # matches countries with the trailing period, so every address needs one.
        pub = make_wos_pub(
            authors=[Author(name="Kaya, Ali", affiliations=[Affiliation(name="Ege University, Izmir, Turkey.", country="Turkey")])],
        )
        assert wos_fields(generate_wos_plaintext([pub]))["C1"] == ["[Kaya, A] Ege University, Izmir, Turkey."]

    def test_c1_appends_the_stored_country_when_the_text_lacks_it(self):
        pub = make_wos_pub(
            source_database="openalex",
            authors=[Author(name="Sofia Demir", affiliations=[Affiliation(name="Hacettepe University", country="Turkey")])],
        )
        assert wos_fields(generate_wos_plaintext([pub]))["C1"] == ["[Demir, S] Hacettepe University, Turkey."]

    def test_c1_does_not_append_a_country_the_text_already_names_by_alias(self):
        pub = make_wos_pub(
            authors=[Author(name="Patel, James", affiliations=[Affiliation(name="University of Oxford, Oxford, England", country="UK")])],
        )
        assert wos_fields(generate_wos_plaintext([pub]))["C1"] == ["[Patel, J] University of Oxford, Oxford, England."]

    def test_doi_references_outside_the_export_stay_bare(self):
        pub = make_wos_pub(external_references=["10.1000/cited-one", "10.1000/CITED-two"])
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert fields["CR"] == ["DOI 10.1000/cited-one", "DOI 10.1000/cited-two"]
        assert fields["NR"] == ["2"]

    def test_in_corpus_references_use_the_wos_cited_reference_form(self):
        # bibliometrix histNetwork matches "AU, PY, SO" plus the DOI against each
        # record's SR, so a bare "DOI x" can never produce a local citation.
        cited = make_wos_pub(pmid="W100", doi="10.1000/In-Corpus", source_database="openalex")
        citing = make_wos_pub(
            pmid="W200",
            doi="10.1000/citing",
            source_database="openalex",
            external_references=["W100", "W999", "10.1000/outside"],
        )
        fields = wos_fields(generate_wos_plaintext([citing, cited]))
        assert fields["CR"] == [
            "DEMIR SA, 2019, MEDICAL EDUCATION, DOI 10.1000/in-corpus",
            "DOI 10.1000/outside",
        ]
        assert fields["NR"] == ["3"]

    def test_a_doi_reference_to_an_exported_record_also_gets_the_full_form(self):
        cited = make_wos_pub(pmid="1", doi="10.1000/in-corpus", journal_name="Med Teach", year=2021)
        citing = make_wos_pub(pmid="2", doi="10.1000/citing", external_references=["10.1000/IN-CORPUS", "1"])
        fields = wos_fields(generate_wos_plaintext([citing, cited]))
        assert fields["CR"] == ["DEMIR SA, 2021, MED TEACH, DOI 10.1000/in-corpus"]

    def test_full_form_leaves_out_parts_the_cited_record_lacks(self):
        cited = make_wos_pub(pmid="1", doi="10.1000/bare", authors=[], year=None, journal_name=None)
        citing = make_wos_pub(pmid="2", doi="10.1000/citing", external_references=["1"])
        assert wos_fields(generate_wos_plaintext([citing, cited]))["CR"] == ["DOI 10.1000/bare"]

    def test_unresolvable_references_leave_cr_out_but_nr_counts_them(self):
        pub = make_wos_pub(source_database="sample", external_references=["sample-001", "sample-002"])
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert "CR" not in fields
        assert fields["NR"] == ["2"]

    def test_no_cr_or_nr_when_the_source_gave_no_references(self):
        fields = wos_fields(generate_wos_plaintext([make_wos_pub(external_references=None)]))
        assert "CR" not in fields
        assert "NR" not in fields

    def test_a_legacy_non_list_reference_value_is_not_iterated_as_characters(self):
        pub = make_wos_pub(external_references="10.1000/legacy-string")
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert "CR" not in fields
        assert "NR" not in fields
        assert wos_reference_coverage([pub]) == (0, 0)

    def test_times_cited_comes_from_citation_count(self):
        assert wos_fields(generate_wos_plaintext([make_wos_pub(citation_count=12)]))["TC"] == ["12"]
        assert wos_fields(generate_wos_plaintext([make_wos_pub(citation_count=0)]))["TC"] == ["0"]
        assert "TC" not in wos_fields(generate_wos_plaintext([make_wos_pub(citation_count=None)]))

    def test_identifiers_year_and_source(self):
        fields = wos_fields(generate_wos_plaintext([make_wos_pub()]))
        assert fields["PY"] == ["2019"]
        assert fields["DI"] == ["10.1111/medu.13900"]
        assert fields["PM"] == ["31234567"]
        assert fields["UT"] == ["PUBMED:31234567"]
        assert fields["SO"] == ["Medical Education"]
        assert fields["SN"] == ["0308-0110"]
        assert fields["EI"] == ["1365-2923"]

    def test_pm_only_for_pubmed_records_because_other_sources_store_their_own_id(self):
        pub = make_wos_pub(pmid="W123", source_database="openalex")
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert "PM" not in fields
        assert fields["UT"] == ["OPENALEX:W123"]

    def test_author_keywords_in_de_and_mesh_in_id(self):
        fields = wos_fields(generate_wos_plaintext([make_wos_pub()]))
        assert fields["DE"] == ["feedback; simulation"]
        assert fields["ID"] == ["Education, Medical; Humans"]

    def test_utf8_text_round_trips(self):
        pub = make_wos_pub(
            title="Tıp eğitiminde geri bildirim: 医学教育",
            authors=[Author(name="Çelik, Ömer", affiliations=[Affiliation(name="Ege Üniversitesi, İzmir, Türkiye")])],
        )
        text = generate_wos_plaintext([pub])
        decoded = text.encode("utf-8").decode("utf-8")
        fields = wos_fields(decoded)
        assert fields["TI"] == ["Tıp eğitiminde geri bildirim: 医学教育"]
        assert fields["AU"] == ["Çelik, Ö"]
        assert fields["C1"] == ["[Çelik, Ö] Ege Üniversitesi, İzmir, Türkiye."]

    def test_missing_fields_produce_no_empty_tags(self):
        pub = make_wos_pub(
            doi=None,
            abstract=None,
            year=None,
            citation_count=None,
            journal_name=None,
            publication_type=None,
            keywords=[],
            authors=[],
            source_database="sample",
        )
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert set(fields) == {"PT", "TI", "UT"}

    def test_blank_values_are_skipped_rather_than_written_as_empty_lines(self):
        pub = make_wos_pub(
            authors=[
                Author(name="  ", affiliations=[Affiliation(name="Orphan University, Turkey")]),
                Author(name="Kaya, Ali", affiliations=[Affiliation(name=" ")]),
            ],
            keywords=[Keyword(term=" ", type=KeywordType.author_keyword)],
        )
        fields = wos_fields(generate_wos_plaintext([pub]))
        assert fields["AU"] == ["Kaya, A"]
        assert "DE" not in fields
        assert "C1" not in fields

    def test_records_are_separated_by_er_and_a_blank_line(self):
        pubs = [make_wos_pub(pmid="1", doi="10.1/a"), make_wos_pub(pmid="2", doi="10.1/b")]
        text = generate_wos_plaintext(pubs)
        records = parse_wos(text)
        assert [dict(r)["UT"] for r in records] == [["PUBMED:1"], ["PUBMED:2"]]
        assert "\nER\n\nPT J\n" in text

    def test_newlines_in_values_cannot_inject_tags_or_records(self):
        pub = make_wos_pub(
            title="Normal\nER\n\nPT J\nTI injected",
            abstract="Line one\r\nLine two",
            authors=[Author(name="Evil\nER", affiliations=[Affiliation(name="Univ\nEF")])],
        )
        text = generate_wos_plaintext([pub])
        records = parse_wos(text)
        assert len(records) == 1
        fields = dict(records[0])
        assert fields["TI"] == ["Normal ER PT J TI injected"]
        assert fields["AB"] == ["Line one Line two"]

    @pytest.mark.parametrize("separator", ["\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", " ", " "])
    def test_unicode_line_separators_are_replaced_too(self, separator):
        pub = make_wos_pub(title=f"Before{separator}ER{separator}After")
        text = generate_wos_plaintext([pub])
        assert wos_fields(text)["TI"] == ["Before ER After"]
        assert text.splitlines() == text.removesuffix("\n").split("\n")
        assert "TI  - Before ER After" in generate_ris([pub])


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
        assert any("-wos-" in name and name.endswith(".txt") for name in names)
        assert any(name.endswith(".svg") for name in names)
        assert "MANIFEST.txt" in names

    def test_bundle_wos_file_matches_the_standalone_export(self):
        pub = make_wos_pub(external_references=["10.1000/cited-one", "sample-x"])
        bundle_bytes = generate_bundle("Bundle Project", [pub], [make_step()], {})
        zf = zipfile.ZipFile(io.BytesIO(bundle_bytes))
        wos_name = next(name for name in zf.namelist() if "-wos-" in name)
        assert zf.read(wos_name).decode("utf-8") == generate_wos_plaintext([pub])
        manifest = zf.read("MANIFEST.txt").decode("utf-8")
        assert f"{wos_name} (1 records, Web of Science plain text; CR lists 1 of 2 cited references" in manifest

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

    def test_fetch_step_lists_records_that_failed_to_persist(self):
        steps = [
            make_step(query_id=1, step_order=1, phase="search", records_in=0, records_out=3, records_affected=3),
            make_step(
                query_id=1, step_order=2, phase="fetch", records_in=3, records_out=2, records_affected=1,
                parameters={
                    "persist_failed": 1,
                    "persist_failures": [
                        {"source_id": "W2302", "source_database": "openalex", "error": "ValueError: boom"},
                    ],
                },
            ),
        ]
        text = generate_methodology("Failure Project", steps)
        assert "Failed to persist: 1 record(s)" in text
        assert "W2302 (openalex): ValueError: boom" in text

    def test_fetch_step_reports_total_and_omitted_count_when_failure_list_is_capped(self):
        steps = [
            make_step(
                query_id=1, step_order=1, phase="fetch", records_in=150, records_out=0, records_affected=150,
                parameters={
                    "persist_failed": 150,
                    "persist_failures": [
                        {"source_id": f"W{i}", "source_database": "openalex", "error": "ValueError: boom"}
                        for i in range(100)
                    ],
                },
            ),
        ]
        text = generate_methodology("Capped Project", steps)
        assert "Failed to persist: 150 record(s)" in text
        assert "W99 (openalex)" in text
        assert "... 50 more not listed" in text

    def test_fetch_step_without_persist_failures_omits_failure_line(self):
        steps = [
            make_step(query_id=1, step_order=1, phase="fetch", records_in=3, records_out=3, records_affected=0,
                      parameters={"persist_failed": 0, "persist_failures": []}),
        ]
        text = generate_methodology("Clean Project", steps)
        assert "Failed to persist" not in text

    def test_search_step_reports_request_rate_limit(self):
        steps = [
            make_step(query_id=1, step_order=1, phase="search", records_out=5,
                      parameters={"query": "x", "rate_limit_per_second": 10.0}),
        ]
        text = generate_methodology("Rate Project", steps)
        assert "    Request rate limit: 10 requests/s" in text

    def test_search_step_reports_fractional_rate_without_rounding(self):
        steps = [
            make_step(query_id=1, step_order=1, phase="search", records_out=5,
                      parameters={"rate_limit_per_second": 0.5}),
        ]
        assert "Request rate limit: 0.5 requests/s" in generate_methodology("Slow Project", steps)

    def test_search_step_without_rate_omits_rate_line(self):
        steps = [make_step(query_id=1, step_order=1, phase="search", records_out=5, parameters={"query": "x"})]
        assert "Request rate limit" not in generate_methodology("No Rate Project", steps)

    def test_no_steps_returns_placeholder_and_no_studies_line(self):
        text = generate_methodology("Empty Project", [])
        assert "No methodology steps recorded" in text
        assert "Studies included" not in text


class TestGenerateMethodologyScreeningStages:
    STEPS = [make_step(query_id=1, step_order=1, phase="search", records_in=0, records_out=20, records_affected=20)]

    def test_reports_each_stage_with_per_reason_counts(self):
        summary = {
            ("title_abstract", "non_english"): 3,
            ("title_abstract", "wrong_population"): 1,
            ("full_text", "wrong_outcome"): 2,
            ("full_text", "fulltext_unavailable"): 1,
        }
        text = generate_methodology("Staged", self.STEPS, summary)
        section = text.split("SCREENING DECISIONS BY STAGE (PRISMA 2020 item 16a)", 1)[1].split("FINAL DATASET", 1)[0]
        assert section.splitlines()[1:8] == [
            "  Title/abstract screening: 4 records excluded",
            "    Non-English language: 3",
            "    Wrong population: 1",
            "  Full-text retrieval: 1 report not retrieved",
            "  Full-text eligibility: 2 reports excluded",
            "    Wrong outcome: 2",
            "",
        ]

    def test_reports_zero_counts_for_a_stage_without_exclusions(self):
        text = generate_methodology("TA only", self.STEPS, {("title_abstract", "other"): 1})
        assert "Title/abstract screening: 1 record excluded" in text
        assert "Full-text retrieval: 0 reports not retrieved" in text
        assert "Full-text eligibility: 0 reports excluded" in text

    def test_notes_exclusions_without_a_recorded_stage(self):
        text = generate_methodology("Legacy", self.STEPS, {"non_english": 2, None: 1})
        assert "Title/abstract screening: 3 records excluded" in text
        assert "3 exclusion(s) have no recorded screening stage and are counted at title/abstract" in text

    def test_notes_stageless_fulltext_unavailable_as_reports_not_retrieved(self):
        text = generate_methodology("Legacy", self.STEPS, {"non_english": 2, (None, "fulltext_unavailable"): 1})
        assert "Title/abstract screening: 2 records excluded" in text
        assert "Full-text retrieval: 1 report not retrieved" in text
        assert (
            "3 exclusion(s) have no recorded screening stage: 1 with reason full-text unavailable "
            "are counted as reports not retrieved, 2 at title/abstract."
        ) in text

    def test_omits_unrecorded_note_when_every_exclusion_has_a_stage(self):
        text = generate_methodology("Staged", self.STEPS, {("full_text", "other"): 1})
        assert "no recorded screening stage" not in text

    def test_reports_stage_section_with_zero_counts_when_nothing_excluded(self):
        text = generate_methodology("Unscreened", self.STEPS, {})
        assert "Title/abstract screening: 0 records excluded" in text
        assert "Full-text eligibility: 0 reports excluded" in text


class TestGenerateMethodologyAuthorProductivity:
    STEPS = [make_step(query_id=1, step_order=1, phase="search", records_in=0, records_out=20, records_affected=20)]

    @staticmethod
    def _section(text: str) -> list[str]:
        return text.split("AUTHOR PRODUCTIVITY (Lotka's law)\n", 1)[1].split("\n\n", 1)[0].splitlines()

    def test_reports_fit_parameters_and_ks_verdict(self):
        counts = [n for n, a in {1: 3600, 2: 900, 3: 400, 4: 225, 5: 144, 6: 100}.items() for _ in range(a)]
        lotka = fit_lotka(counts)
        text = generate_methodology("Lotka", self.STEPS, {}, author_productivity=lotka)
        assert self._section(text) == [
            f"  Method: {LOTKA_METHOD}",
            (
                "  Parameters: complete counting over included records; at least 3 productivity levels; "
                "K-S at the 0.01 level, critical value 1.63/sqrt(N), used only above 35 authors"
            ),
            "  Authors: 5369 across 6 productivity levels",
            "  Distribution (papers: authors): 1: 3600, 2: 900, 3: 400, 4: 225, 5: 144, 6: 100",
            "  Fit: alpha = 2.0, C = 3600.0, R^2 = 1.0",
            (
                "  Kolmogorov-Smirnov: D = 0.0933, critical value = 0.0222 at the 0.01 level; "
                "consistent with Lotka's law: no"
            ),
        ]

    def test_states_why_no_fit_was_made(self):
        text = generate_methodology("Small", self.STEPS, {}, author_productivity=fit_lotka([1, 1, 2]))
        section = self._section(text)
        assert "  Authors: 3 across 2 productivity levels" in section
        assert "  Distribution (papers: authors): 1: 2, 2: 1" in section
        assert any(line.startswith("  Fit: not computed. ") and "3 distinct" in line for line in section)
        assert not any(line.startswith("  Kolmogorov-Smirnov:") for line in section)

    def test_omits_the_distribution_line_without_authors(self):
        section = self._section(generate_methodology("None", self.STEPS, {}, author_productivity=fit_lotka([])))
        assert "  Authors: 0 across 0 productivity levels" in section
        assert not any(line.startswith("  Distribution") for line in section)

    def test_states_why_the_ks_verdict_is_missing(self):
        counts = [n for n, a in {1: 20, 2: 5, 3: 2, 4: 1}.items() for _ in range(a)]
        section = self._section(generate_methodology("Few", self.STEPS, {}, author_productivity=fit_lotka(counts)))
        ks_line = next(line for line in section if line.startswith("  Kolmogorov-Smirnov:"))
        assert ks_line.startswith("  Kolmogorov-Smirnov: D = ")
        assert "no verdict" in ks_line and "35" in ks_line

    def test_states_why_the_ks_test_was_not_run(self):
        counts = [n for n, a in {1: 5, 2: 6, 3: 8, 4: 9}.items() for _ in range(a)]
        section = self._section(generate_methodology("Rising", self.STEPS, {}, author_productivity=fit_lotka(counts)))
        ks_line = next(line for line in section if line.startswith("  Kolmogorov-Smirnov:"))
        assert ks_line.startswith("  Kolmogorov-Smirnov: not computed. ")
        assert "alpha > 1" in ks_line

    def test_omits_the_section_when_no_author_analysis_is_given(self):
        assert "AUTHOR PRODUCTIVITY" not in generate_methodology("Plain", self.STEPS, {})

    def test_bundle_methodology_carries_the_section(self):
        data = generate_bundle("Bundle", [make_pub()], self.STEPS, {}, author_productivity=fit_lotka([1]))
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if "methodology" in n)
            assert "AUTHOR PRODUCTIVITY (Lotka's law)" in zf.read(name).decode("utf-8")


class TestScreeningStageInJson:
    def test_publication_entry_carries_screening_stage(self):
        pub = make_pub(excluded=True, exclusion_reason="wrong_outcome", screening_stage="full_text")
        entry = json.loads(generate_json("P", [pub]))["publications"][0]
        assert entry["screening_stage"] == "full_text"

    def test_included_publication_has_null_screening_stage(self):
        entry = json.loads(generate_json("P", [make_pub()]))["publications"][0]
        assert entry["screening_stage"] is None


# ---------------------------------------------------------------------------
# Screening decision audit trail (issue #120)
# ---------------------------------------------------------------------------


def make_decision(
    *,
    decision_id,
    decided_at,
    publication,
    previous=(False, None, None),
    new=(True, "other", "title_abstract"),
    reviewer=None,
    source="toggle",
    criteria=None,
    run_id=None,
):
    decision = ScreeningDecision(
        id=decision_id,
        project_id=1,
        publication_id=decision_id * 10,
        decided_at=decided_at,
        reviewer=reviewer,
        source=source,
        run_id=run_id,
        criteria=criteria,
        previous_excluded=previous[0],
        previous_exclusion_reason=previous[1],
        previous_screening_stage=previous[2],
        excluded=new[0],
        exclusion_reason=new[1],
        screening_stage=new[2],
    )
    decision.publication = publication
    return decision


def _utc(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


P1 = make_pub(pmid="111", doi="10.1/one")
P2 = make_pub(pmid="222", doi=None)
P3 = make_pub(pmid="=333", doi="10.1/three")
P4 = make_pub(pmid="444", doi="10.1/four")
BULK = {"source": "bulk_exclude", "criteria": {"citation_threshold": 0}}

DECISIONS = (
    make_decision(decision_id=1, decided_at=_utc(1, 9), publication=P1,
                  new=(True, "non_english", "title_abstract"), reviewer="Reviewer A"),
    make_decision(decision_id=2, decided_at=_utc(1, 9, 5), publication=P2, **BULK),
    make_decision(decision_id=3, decided_at=_utc(1, 9, 5), publication=P3, **BULK),
    make_decision(decision_id=4, decided_at=_utc(2, 10), publication=P1,
                  previous=(True, "non_english", "title_abstract"), new=(False, None, None), reviewer="MB"),
    make_decision(decision_id=5, decided_at=_utc(3, 11, 30), publication=P4,
                  new=(True, "wrong_outcome", "full_text"), reviewer="Reviewer A"),
    make_decision(decision_id=6, decided_at=_utc(3, 12), publication=P4,
                  previous=(True, "wrong_outcome", "full_text"), new=(True, "fulltext_unavailable", "full_text"),
                  reviewer="MB"),
)

NOT_BACKFILLED = (
    "  Not backfilled: decisions made before the audit trail existed (Alembic revision "
    "0006_screening_decisions) were not recorded."
)


def _decision_section(text):
    return text.split("SCREENING DECISION HISTORY (audit trail)\n", 1)[1].split("\n\n", 1)[0].splitlines()


class TestScreeningDecisionHistory:
    STEPS = [make_step(query_id=1, step_order=1, phase="search", records_in=0, records_out=20, records_affected=20)]

    def test_summarises_counts_reversals_timestamps_and_reviewers(self):
        log = ScreeningDecisionLog(decisions=DECISIONS, unlogged_exclusions=1)
        text = generate_methodology("Audit", self.STEPS, {}, log)
        assert _decision_section(text) == [
            "  Decisions logged: 6",
            "    Exclusions: 4",
            "    Reversals (excluded record re-included): 1",
            "    Reason or stage changes: 1",
            "  First decision: 2026-10-01T09:00:00Z",
            "  Last decision: 2026-10-03T12:00:00Z",
            "  Exclusion decisions by stage and reason:",
            "    Title/abstract: 3",
            "      Other / unspecified: 2",
            "      Non-English language: 1",
            "    Full text: 2",
            "      Full-text not retrievable: 1",
            "      Wrong outcome: 1",
            "  Bulk exclusions:",
            (
                "    2026-10-01T09:05:00Z (run id not recorded): 2 records excluded with citation count missing "
                "or at most 0 (reason: Other / unspecified; stage: Title/abstract; reviewer: none recorded)"
            ),
            "  Reviewer labels: MB, Reviewer A",
            "  Decisions without a reviewer label: 2",
            "  Per-decision log: the screening-decisions CSV in the export bundle.",
            NOT_BACKFILLED,
            "    1 currently excluded record has no logged decision.",
        ]

    def test_section_sits_between_the_stage_counts_and_the_final_dataset(self):
        text = generate_methodology("Audit", self.STEPS, {}, ScreeningDecisionLog(decisions=DECISIONS))
        stage = text.index("SCREENING DECISIONS BY STAGE")
        history = text.index("SCREENING DECISION HISTORY (audit trail)")
        final = text.index("FINAL DATASET")
        assert stage < history < final

    def test_empty_log_still_states_that_nothing_was_backfilled(self):
        text = generate_methodology("Audit", self.STEPS, {}, ScreeningDecisionLog(decisions=(), unlogged_exclusions=3))
        assert _decision_section(text) == [
            "  Decisions logged: 0",
            NOT_BACKFILLED,
            "    3 currently excluded records have no logged decision.",
        ]

    def test_omits_the_unlogged_line_when_every_exclusion_is_logged(self):
        text = generate_methodology("Audit", self.STEPS, {}, ScreeningDecisionLog(decisions=DECISIONS))
        assert _decision_section(text)[-1] == NOT_BACKFILLED

    def test_unknown_reason_and_missing_stage_are_reported_verbatim(self):
        decisions = (
            make_decision(decision_id=1, decided_at=_utc(1, 9), publication=P1, new=(True, "legacy_reason", None)),
            make_decision(decision_id=2, decided_at=_utc(1, 10), publication=P2, new=(True, "other", "legacy_stage")),
        )
        text = generate_methodology("Audit", self.STEPS, {}, ScreeningDecisionLog(decisions=decisions))
        section = _decision_section(text)
        breakdown = section[section.index("  Exclusion decisions by stage and reason:") + 1:][:4]
        assert breakdown == [
            "    No stage recorded: 1",
            "      legacy_reason: 1",
            "    legacy_stage: 1",
            "      Other / unspecified: 1",
        ]

    def test_bulk_criteria_other_than_a_citation_threshold_are_printed_verbatim(self):
        decisions = (
            make_decision(decision_id=1, decided_at=_utc(1, 9), publication=P1, source="bulk_exclude",
                          criteria={"year_before": 2000}),
            make_decision(decision_id=2, decided_at=_utc(1, 10), publication=P2, source="bulk_exclude",
                          new=(True, None, "full_text"), reviewer="MB"),
        )
        text = generate_methodology("Audit", self.STEPS, {}, ScreeningDecisionLog(decisions=decisions))
        section = _decision_section(text)
        assert (
            "    2026-10-01T09:00:00Z (run id not recorded): 1 record excluded with "
            "criteria {\"year_before\": 2000} "
            "(reason: Other / unspecified; stage: Title/abstract; reviewer: none recorded)"
        ) in section
        assert (
            "    2026-10-01T10:00:00Z (run id not recorded): 1 record excluded with criteria not recorded "
            "(reason: No reason recorded; stage: Full text; reviewer: MB)"
        ) in section

    def test_log_of_only_re_inclusions_has_no_exclusion_breakdown(self):
        decision = make_decision(decision_id=1, decided_at=_utc(1, 9), publication=P1,
                                 previous=(True, "other", "title_abstract"), new=(False, None, None))
        section = _decision_section(
            generate_methodology("Audit", self.STEPS, {}, ScreeningDecisionLog(decisions=(decision,)))
        )
        assert "    Reversals (excluded record re-included): 1" in section
        assert "  Exclusion decisions by stage and reason:" not in section
        assert "  Bulk exclusions:" not in section

    def test_naive_timestamps_are_read_as_utc(self):
        decision = make_decision(decision_id=1, decided_at=datetime(2026, 10, 1, 9, 0), publication=P1)
        text = generate_methodology("Audit", self.STEPS, {}, ScreeningDecisionLog(decisions=(decision,)))
        assert "  First decision: 2026-10-01T09:00:00Z" in _decision_section(text)

    def test_omitted_when_no_log_is_passed(self):
        assert "SCREENING DECISION HISTORY" not in generate_methodology("Audit", self.STEPS, {})

    def test_no_steps_project_still_reports_logged_decisions(self):
        text = generate_methodology("Audit", [], None, ScreeningDecisionLog(decisions=DECISIONS[:1]))
        assert "No methodology steps recorded" in text
        assert "  Decisions logged: 1" in _decision_section(text)

    def test_no_steps_project_without_decisions_keeps_the_placeholder_only(self):
        text = generate_methodology("Audit", [], None, ScreeningDecisionLog(decisions=()))
        assert "SCREENING DECISION HISTORY" not in text


class TestScreeningDecisionsCsv:
    HEADER = [
        "decision_id", "decided_at_utc", "reviewer", "source", "run_id", "action", "criteria",
        "publication_id", "pmid", "doi",
        "previous_excluded", "previous_exclusion_reason", "previous_screening_stage",
        "excluded", "exclusion_reason", "screening_stage",
    ]

    def _rows(self, decisions):
        return list(csv.reader(io.StringIO(generate_screening_decisions_csv(decisions))))

    def test_writes_one_row_per_decision_in_order(self):
        header, *rows = self._rows(DECISIONS)
        assert header == self.HEADER
        assert [r[0] for r in rows] == ["1", "2", "3", "4", "5", "6"]
        assert [r[5] for r in rows] == ["exclude", "exclude", "exclude", "re-include", "exclude", "change"]

    def test_writes_exact_row_content(self):
        _, first, second, _, fourth, *_ = self._rows(DECISIONS)
        assert first == [
            "1", "2026-10-01T09:00:00.000000Z", "Reviewer A", "toggle", "", "exclude", "",
            "10", "111", "10.1/one", "false", "", "", "true", "non_english", "title_abstract",
        ]
        assert second[6] == '{"citation_threshold": 0}'
        assert second[9] == ""
        assert fourth[10:] == ["true", "non_english", "title_abstract", "false", "", ""]

    def test_escapes_formula_injection_in_identifiers(self):
        _, _, _, third, *_ = self._rows(DECISIONS)
        assert third[8] == "'=333"

    def test_empty_log_writes_only_the_header(self):
        assert self._rows(()) == [self.HEADER]


class TestBundleScreeningDecisions:
    def test_bundle_carries_the_decision_csv_and_lists_it_in_the_manifest(self):
        log = ScreeningDecisionLog(decisions=DECISIONS)
        zf = zipfile.ZipFile(io.BytesIO(generate_bundle("Bundle Project", [make_pub()], [make_step()], {}, log)))
        (csv_name,) = [n for n in zf.namelist() if "screening-decisions" in n]
        assert csv_name.endswith(".csv")
        assert zf.read(csv_name).decode("utf-8") == generate_screening_decisions_csv(DECISIONS)
        manifest = zf.read("MANIFEST.txt").decode("utf-8")
        assert f"{csv_name} (6 decisions)" in manifest
        methodology_name = next(n for n in zf.namelist() if "methodology" in n)
        assert "SCREENING DECISION HISTORY" in zf.read(methodology_name).decode("utf-8")

    def test_bundle_without_a_log_has_no_decision_csv(self):
        zf = zipfile.ZipFile(io.BytesIO(generate_bundle("Bundle Project", [make_pub()], [make_step()], {})))
        assert not [n for n in zf.namelist() if "screening-decisions" in n]


RUN_A = "11111111-1111-4111-8111-111111111111"
RUN_B = "22222222-2222-4222-8222-222222222222"
RUN_C = "33333333-3333-4333-8333-333333333333"


def make_bulk_step(*, run_id, at, matched, excluded, query_id=1, step_order=9, included_before=20,
                   reason="other", stage="title_abstract", reviewer=None):
    step = make_step(
        query_id=query_id, step_order=step_order, phase="bulk_exclude", source="bulk_exclude",
        action="Bulk exclusion", records_in=included_before, records_out=included_before - excluded,
        records_affected=excluded,
        parameters={
            "run_id": run_id, "scope": "project", "citation_threshold": 0, "matched": matched,
            "excluded": excluded, "skipped": matched - excluded, "reason": reason,
            "screening_stage": stage, "reviewer": reviewer,
        },
    )
    step.timestamp = at
    return step


def _bulk_section_lines(text):
    section = _decision_section(text)
    start = section.index("  Bulk exclusions:") + 1
    return [line for line in section[start:] if line.startswith("    ")]


class TestBulkExclusionRuns:
    PIPELINE = [
        make_step(query_id=1, step_order=1, phase="search", records_in=0, records_out=20, records_affected=20),
        make_step(query_id=1, step_order=2, phase="fetch", records_in=20, records_out=18, records_affected=2),
    ]

    def _bulk_rows(self, run_id, at, count, first_id=1):
        return tuple(
            make_decision(decision_id=first_id + i, decided_at=at, publication=P1, source="bulk_exclude",
                          criteria={"citation_threshold": 0}, run_id=run_id)
            for i in range(count)
        )

    def test_a_zero_match_run_is_reported_from_its_methodology_step(self):
        steps = self.PIPELINE + [make_bulk_step(run_id=RUN_A, at=_utc(4, 8), matched=0, excluded=0, reviewer="MB")]
        text = generate_methodology("Audit", steps, {}, ScreeningDecisionLog(decisions=()))
        section = _decision_section(text)
        assert section[0] == "  Decisions logged: 0"
        assert section[1:3] == [
            "  Bulk exclusions:",
            f"    2026-10-04T08:00:00Z (run {RUN_A}): 0 matched, 0 excluded, 0 skipped; citation count missing "
            "or at most 0 (reason: Other / unspecified; stage: Title/abstract; reviewer: MB)",
        ]

    def test_runs_are_grouped_by_run_id_not_by_timestamp(self):
        same_moment = _utc(5, 9)
        decisions = self._bulk_rows(RUN_A, same_moment, 2) + self._bulk_rows(RUN_B, same_moment, 1, first_id=3)
        steps = self.PIPELINE + [
            make_bulk_step(run_id=RUN_A, at=same_moment, matched=2, excluded=2),
            make_bulk_step(run_id=RUN_B, at=same_moment, matched=1, excluded=1, step_order=10),
        ]
        lines = _bulk_section_lines(generate_methodology("Audit", steps, {}, ScreeningDecisionLog(decisions=decisions)))
        assert [line.split(": ", 1)[1].split(";", 1)[0] for line in lines[:2]] == [
            "2 matched, 2 excluded, 0 skipped",
            "1 matched, 1 excluded, 0 skipped",
        ]
        assert RUN_A in lines[0] and RUN_B in lines[1]

    def test_rows_whose_run_has_no_step_are_still_reported(self):
        decisions = self._bulk_rows(RUN_C, _utc(6, 7), 2)
        lines = _bulk_section_lines(generate_methodology("Audit", self.PIPELINE, {}, ScreeningDecisionLog(decisions)))
        assert lines == [
            f"    2026-10-06T07:00:00Z (run {RUN_C}, no methodology step recorded): 2 records excluded with "
            "citation count missing or at most 0 (reason: Other / unspecified; stage: Title/abstract; "
            "reviewer: none recorded)",
        ]

    def test_a_step_that_disagrees_with_its_decision_rows_is_flagged(self):
        decisions = self._bulk_rows(RUN_A, _utc(5, 9), 1)
        steps = self.PIPELINE + [make_bulk_step(run_id=RUN_A, at=_utc(5, 9), matched=2, excluded=2)]
        lines = _bulk_section_lines(generate_methodology("Audit", steps, {}, ScreeningDecisionLog(decisions)))
        assert lines[1] == "      Note: 1 decision row carries this run id, but the step records 2 exclusion(s)."

    def test_bulk_steps_stay_out_of_the_pipeline_and_the_included_total(self):
        bulk = make_bulk_step(run_id=RUN_A, at=_utc(4, 8), matched=3, excluded=3, included_before=18)
        with_bulk = generate_methodology("Audit", self.PIPELINE + [bulk], {}, ScreeningDecisionLog(decisions=()))
        without_bulk = generate_methodology("Audit", self.PIPELINE, {}, ScreeningDecisionLog(decisions=()))
        assert "BULK_EXCLUDE" not in with_bulk
        assert "Step 9" not in with_bulk
        assert "  Studies included: 18" in with_bulk
        assert with_bulk.split("FINAL DATASET", 1)[1] == without_bulk.split("FINAL DATASET", 1)[1]

    def test_bulk_steps_do_not_change_the_prisma_diagram(self):
        bulk = make_bulk_step(run_id=RUN_A, at=_utc(4, 8), matched=3, excluded=3, included_before=18)
        assert generate_prisma_svg("Audit", self.PIPELINE + [bulk], {}) == generate_prisma_svg("Audit", self.PIPELINE, {})

    def test_a_project_with_only_a_bulk_step_still_gets_the_history_section(self):
        steps = [make_bulk_step(run_id=RUN_A, at=_utc(4, 8), matched=0, excluded=0)]
        text = generate_methodology("Audit", steps)
        assert "No methodology steps recorded" in text
        assert f"(run {RUN_A}): 0 matched, 0 excluded, 0 skipped" in text

    def test_csv_carries_the_run_id(self):
        (row,) = list(csv.reader(io.StringIO(generate_screening_decisions_csv(self._bulk_rows(RUN_A, _utc(5, 9), 1)))))[1:]
        assert row[3:5] == ["bulk_exclude", RUN_A]
