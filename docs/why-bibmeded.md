# Why BibMedEd?

> The short version: bibliometric reviews in medical education currently require four tools — search, screening, analysis, visualisation — and a fifth (Excel) to glue them together. BibMedEd does all of them in one self-hostable application and writes your PRISMA methodology section as it goes.

## Who this page is for

You arrived here because you were searching for something like *"Covidence alternative"*, *"free VOSviewer replacement"*, *"open-source bibliometric tool"*, or *"how do I run a systematic review without Excel"*. This page is a fair-handed comparison so you can pick the right tool — sometimes that's not BibMedEd.

## The capability matrix

| Capability | BibMedEd | Covidence | VOSviewer | CiteSpace | Bibliometrix (R) | pyBibX |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Multi-database search built-in** | ✅ PubMed + OpenAlex + CrossRef + Semantic Scholar (extensible) | ❌ (import only) | ❌ (import only) | ❌ (import only) | ⚠️ via WoS/Scopus importers | ❌ (file import) |
| **Automatic cross-source dedup** | ✅ DOI + PMID | ✅ | ❌ | ❌ | ⚠️ manual | ❌ |
| **Screening workflow** | 📋 single-reviewer with PRISMA-2020 exclusion reasons (dual planned) | ✅ dual-reviewer | ❌ | ❌ | ❌ | ❌ |
| **Bibliometric analyses** | ✅ 6 modules + h/g/e-index, coupling, co-citation, burst detection, field maturity | ❌ | ⚠️ network only | ✅ many | ✅ many | ✅ many + AI |
| **Network visualisation** | ✅ D3.js interactive | ❌ | ✅ desktop | ✅ desktop | ✅ static | ✅ static |
| **PRISMA-ready methodology log** | ✅ auto-generated | ✅ manual | ❌ | ❌ | ❌ | ❌ |
| **Self-hostable** | ✅ `docker compose up` | ❌ SaaS only | ✅ desktop binary | ✅ desktop binary | ✅ R/RStudio | ✅ Python lib |
| **Web UI for non-programmers** | ✅ | ✅ | ✅ desktop | ✅ desktop | ⚠️ R Shiny (biblioshiny) | ❌ Python only |
| **API for programmatic access** | ✅ FastAPI / OpenAPI | ⚠️ limited | ❌ | ❌ | ⚠️ R only | ✅ Python |
| **Extensible to new data sources** | ✅ ~50-line adapter | ❌ | ❌ | ❌ | ❌ | ❌ |
| **License** | MIT | Proprietary | Free (closed-source) | Free (closed-source) | GPL-3 | MIT |
| **Cost** | Free | Paid per seat | Free | Free | Free | Free |

Legend: ✅ first-class · ⚠️ partial · 📋 on roadmap · ❌ not supported.

## When to pick which tool

### Pick BibMedEd if you want
- One integrated app from search → analysis → export.
- A PRISMA methodology log generated automatically rather than reconstructed at write-up time.
- To self-host on a lab server or a researcher's laptop without per-seat fees.
- To plug in a new bibliographic source (institutional repository, niche database) without negotiating with a vendor.
- A modern web UI usable by non-programmer collaborators in your research group.

### Pick Covidence if you want
- A dual-reviewer screening workflow with conflict resolution and inter-rater reliability metrics — this is Covidence's main strength and BibMedEd hasn't shipped it yet (roadmap item).
- Institutional support contracts and training.
- You can absorb the per-seat or per-review pricing.

### Pick VOSviewer if you want
- A polished, battle-tested desktop tool for network visualisation specifically.
- You already have a deduplicated `.ris` or `.csv` and only need the network.
- Reproducible static images for a publication figure (VOSviewer's rendering is excellent).

### Pick CiteSpace if you want
- Burst detection, dual-map overlay, and timeline visualisations — CiteSpace's signature features.
- Decades of methodological literature behind specific analyses.

### Pick Bibliometrix if you want
- A mature R-native workflow you can pipe through `dplyr` / `ggplot2` / `quarto`.
- The biblioshiny GUI for a no-code experience inside RStudio.
- A vast literature of published methods using the package — peer reviewers will recognise it.

### Pick pyBibX if you want
- Python-native programmatic analysis with built-in LLM-based topic interpretation.
- Notebook-driven workflows where the analysis lives next to your data wrangling.

## Where BibMedEd is honestly weaker today

- **Single-reviewer screening only.** Dual-reviewer with conflict resolution is on the [roadmap](https://github.com/ata381/BibMedEd/blob/master/ROADMAP.md) but Covidence ships it today.
- **Frontend visualisations are interactive but not publication-ready.** VOSviewer and CiteSpace produce better static images for journal figures; BibMedEd exports the underlying data so you can re-render in either if needed.
- **Adapter coverage is still growing.** PubMed, OpenAlex, CrossRef, and Semantic Scholar ship; Europe PMC, arXiv, DOAJ, OpenCitations, CORE, BASE, and Lens.org are open issues waiting on contributors ([adapter label](https://github.com/ata381/BibMedEd/issues?q=is%3Aissue+is%3Aopen+label%3Aadapter)). Scopus and Web of Science require paid API agreements.
- **No published bibliometric methodology paper yet** — JOSS submission is in flight. Bibliometrix's [methodology paper](https://doi.org/10.1016/j.joi.2017.08.007) has thousands of citations; we have zero so far.

We'd rather be honest about these gaps than oversell. If any of them are dealbreakers, pick a tool above and come back when the gap closes (or — better — [open the PR that closes it](https://github.com/ata381/BibMedEd/blob/master/CONTRIBUTING.md)).

## Where BibMedEd is structurally better

- **The methodology log is novel.** No other tool on this list emits a citable text record of every pipeline step — search query, source, retrieval timestamp, dedup decisions, exclusion filters, analysis runs — that you paste straight into your [PRISMA 2020](https://doi.org/10.1136/bmj.n71) Methods section. This isn't a feature you can bolt onto the others.
- **The adapter pattern is the entire extensibility story.** Every other tool above either accepts a fixed set of import formats or is single-source. BibMedEd ships four adapters (PubMed, OpenAlex, CrossRef, Semantic Scholar) at ~50-150 lines each; more are open issues with claim-it labels, and the registry auto-discovers any new `BaseSourceAdapter` dropped into `app/adapters/` — no registration step.
- **Cross-source deduplication is automatic, not "import then dedupe in Excel."** DOI and PMID matching happens at retrieval time and is logged.
- **Web-native, multi-user-ready architecture.** VOSviewer and CiteSpace are desktop tools; Bibliometrix is R-bound; pyBibX is a Python library. BibMedEd is a FastAPI service designed to run on a lab server with shared access — a deployment shape none of the alternatives offer.

## Try it

```bash
git clone https://github.com/ata381/BibMedEd
cd BibMedEd/bibmeded
docker compose up
```

Open [http://localhost:3000](http://localhost:3000). Or click the Render deploy button on the [README](https://github.com/ata381/BibMedEd#deploy-to-cloud) for a zero-install cloud spin-up.

Then read the [case study](case-study.md) for a worked example of what a real bibliometric review looks like end-to-end in BibMedEd.
