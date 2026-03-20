from app.services.pubmed import PubMedClient

def test_parse_missing_abstract():
    xml = '<?xml version="1.0"?><PubmedArticleSet><PubmedArticle><MedlineCitation Status="MEDLINE" Owner="NLM"><PMID Version="1">99999999</PMID><Article PubModel="Print"><Journal><Title>Test Journal</Title><JournalIssue CitedMedium="Print"><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal><ArticleTitle>No Abstract Article</ArticleTitle></Article></MedlineCitation><PubmedData></PubmedData></PubmedArticle></PubmedArticleSet>'
    client = PubMedClient()
    records = client._parse_records(xml)
    assert len(records) == 1
    assert records[0].abstract is None
    assert records[0].title == "No Abstract Article"
    assert records[0].year == 2023

def test_parse_multiple_authors():
    xml = '<?xml version="1.0"?><PubmedArticleSet><PubmedArticle><MedlineCitation Status="MEDLINE" Owner="NLM"><PMID Version="1">11111111</PMID><Article PubModel="Electronic"><Journal><Title>Test</Title><JournalIssue CitedMedium="Internet"><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal><ArticleTitle>Multi Author</ArticleTitle><AuthorList CompleteYN="Y"><Author ValidYN="Y"><LastName>A</LastName><ForeName>B</ForeName></Author><Author ValidYN="Y"><LastName>C</LastName><ForeName>D</ForeName></Author><Author ValidYN="Y"><LastName>E</LastName><ForeName>F</ForeName></Author></AuthorList></Article></MedlineCitation><PubmedData></PubmedData></PubmedArticle></PubmedArticleSet>'
    client = PubMedClient()
    records = client._parse_records(xml)
    assert len(records[0].authors) == 3
    assert records[0].authors[0].name == "A, B"
    assert records[0].authors[2].name == "E, F"

def test_parse_no_references():
    xml = '<?xml version="1.0"?><PubmedArticleSet><PubmedArticle><MedlineCitation Status="MEDLINE" Owner="NLM"><PMID Version="1">22222222</PMID><Article PubModel="Print"><Journal><Title>J</Title><JournalIssue CitedMedium="Print"><PubDate><Year>2022</Year></PubDate></JournalIssue></Journal><ArticleTitle>No Refs</ArticleTitle></Article></MedlineCitation><PubmedData><ReferenceList></ReferenceList></PubmedData></PubmedArticle></PubmedArticleSet>'
    client = PubMedClient()
    records = client._parse_records(xml)
    assert records[0].references == []
