from app.analysis.publications import analyze_publication_trends
from app.analysis.authors import analyze_authors
from app.analysis.countries import analyze_countries
from app.analysis.keywords import analyze_keywords
from app.analysis.citations import analyze_citations
from app.analysis.journals import analyze_journals

ANALYSIS_FUNCTIONS = {
    "publications": analyze_publication_trends,
    "authors": analyze_authors,
    "countries": analyze_countries,
    "keywords": analyze_keywords,
    "citations": analyze_citations,
    "journals": analyze_journals,
}
