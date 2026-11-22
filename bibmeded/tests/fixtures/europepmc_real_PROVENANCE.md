# Europe PMC captured fixtures

The `europepmc_real_*.json` files started as public Europe PMC REST responses
captured on 2026-11-22 (UTC). The idlist page is stored as captured. The two `core`
responses were then **minimised**: they keep only the structure and identifiers the
adapter tests need, and every title, abstract, author name, affiliation, keyword and
ORCID iD in them is synthetic. They are not the API's response bodies any more.

The synthetic fixtures (`europepmc_search_idlist.json`, `europepmc_core_records.json`)
are separate and cover edge cases that real records do not show reliably.

## 1. Capture

Every request was `POST https://www.ebi.ac.uk/europepmc/webservices/rest/searchPOST`
with an `application/x-www-form-urlencoded` body. No credentials, cookies, or `email`
parameter were sent.

| File | Captured (UTC) | Form parameters | HTTP |
|---|---|---|---|
| `europepmc_real_idlist_page.json` | 2026-11-22T16:03:16 | `query=(TITLE:"medical education" AND TITLE:"simulation") AND PUB_YEAR:[2021 TO 2021]`, `resultType=idlist`, `pageSize=5`, `format=json` | 200 |
| `europepmc_real_core_topic.json` | 2026-11-22T16:03:52 | `query=(EXT_ID:34093275 AND SRC:MED) OR (EXT_ID:33086367 AND SRC:MED) OR (EXT_ID:34222746 AND SRC:MED) OR (EXT_ID:34826270 AND SRC:MED) OR (EXT_ID:34011088 AND SRC:MED)`, `resultType=core`, `pageSize=25`, `format=json` | 200 |
| `europepmc_real_core_collections.json` | 2026-11-22T16:03:16 | `query=(EXT_ID:42954961 AND SRC:MED) OR (EXT_ID:PMC13787573 AND SRC:PMC) OR (EXT_ID:CN101548780 AND SRC:PAT) OR (EXT_ID:IND44331483 AND SRC:AGR) OR (EXT_ID:367763 AND SRC:CBA) OR (EXT_ID:410369 AND SRC:HIR) OR (EXT_ID:C8501 AND SRC:CTX) OR (EXT_ID:889149 AND SRC:ETH) OR (EXT_ID:711268 AND SRC:CIT) OR (EXT_ID:PPR1373820 AND SRC:PPR) OR (EXT_ID:NBK623779 AND SRC:NBK)`, `resultType=core`, `pageSize=25`, `format=json` | 200 |

The IDs in the collections query are the first result of `query=SRC:<SRC>`,
`resultType=idlist`, `pageSize=3`, captured the same day for each of the eleven
documented collections: MED, PMC, PAT, AGR, CBA, HIR, CTX, ETH, CIT, PPR, NBK. Each
record came back from its `EXT_ID:<id> AND SRC:<SRC>` clause, which is what the
adapter's collection allow-list relies on.

## 2. Kept as returned

- `europepmc_real_idlist_page.json`: the whole body (identifiers only, no text
  content), written compactly with one trailing newline.
- Both `core` files: the envelope (`version`, `hitCount`, `request`), the order of
  `resultList.result`, and in each record only these fields, with their captured
  values: `id`, `source`, `pmid`, `pmcid`, `doi`, `pubYear`, `pubTypeList`,
  `journalInfo.yearOfPublication`, `journalInfo.journal.{title, issn, essn}`,
  `bookOrReportDetails.yearOfPublication`, and `meshHeadingList.meshHeading[].descriptorName`
  (NLM MeSH descriptors). A field absent from a captured record is still absent.

## 3. Removed

- All other record fields, including `isOpenAccess`, `license`, `authorString`,
  `authorIdList`, the record-level `affiliation`, `fullTextUrlList`, `fullTextIdList`,
  `grantsList`, `patentDetails`, `pageInfo`, dates, `has*`/`in*` flags, and the
  journal's `nlmid`/abbreviations, `bookOrReportDetails.publisher`, and the MeSH
  `majorTopic_YN`/`meshQualifierList`.
- Every captured abstract (4 in the topic file, 9 in the collections file). Eleven of
  the thirteen came from records marked `isOpenAccess: N` with no documented reuse
  terms; none of the captured abstract text is kept anywhere in this repository.
- Every captured title, author name, affiliation, ORCID iD and author keyword. This
  includes the affiliation of `MED:42954961` whose institutional e-mail address had
  already been replaced by `redacted@example.org` in two fields before `4d26c74`.
- In the collections file, all authors after the first in each record (30 to 9);
  that test checks identifiers and collections, not authorship.
- The ORCID on the third ORCID-bearing author of `MED:34011088` (6 to 5 in the topic
  file), because only two example iDs are used (below).

## 4. Synthetic replacements

Each `core` file carries a top-level `_fixture_note` saying the same thing; the
adapter ignores that key.

| Field | Synthetic value |
|---|---|
| `title` | `Synthetic title for <SRC>:<id>` |
| `abstractText` | For abstracts that used `<h4>` section headings, the same heading labels in the same order, each followed by `Synthetic placeholder sentence for the <label> section.`, so the HTML shape matches what Europe PMC serves. Otherwise `Synthetic placeholder abstract for <SRC>:<id>.` `MED:42954961`, whose abstract contained a literal `p<0.05`, also gets `Synthetic statistic (β=0.05; p<0.05).` |
| `authorList.author[].fullName` | `Synthetic Author <n> (<SRC>:<id>)`; the first author of `MED:42954961` is `Synthetic Author Ünal-Çelik (MED:42954961)` to exercise UTF-8 decoding |
| `authorAffiliationDetailsList` | one entry, `Synthetic Department, Example University (author <n>)`, only for authors that had at least one affiliation |
| `authorId` (ORCID) | `0000-0002-1825-0097` and `0000-0002-1694-233X`, the ORCID-published example iDs, in that order for the first two ORCID-bearing authors of a record |
| `keywordList.keyword` | `synthetic keyword <n>`, same count as captured |

The topic file keeps its author count per record (31 authors); the collections file
keeps one author for each record that had any.

## 5. Sizes

| File | Bytes as captured | Bytes stored at `4d26c74` | Bytes stored now |
|---|---|---|---|
| `europepmc_real_idlist_page.json` | 817 | 818 | 818 |
| `europepmc_real_core_topic.json` | 31866 | 31867 | 17721 |
| `europepmc_real_core_collections.json` | 27067 | 27070 | 8383 |

Stored sizes include one trailing newline. The minimised files are pretty-printed
UTF-8 JSON (`indent=2`, non-ASCII written as-is) to keep reviews readable.
