# Community

BibMedEd grows through two kinds of participation: researchers testing it on real workflows, and contributors improving the software and its data-source coverage. Both are valuable, and neither requires a long-term commitment.

## Try it on a research workflow

Start with the bundled synthetic project if you want to explore the analyses without querying an external database. From an empty workspace, choose **Explore sample project** to open a populated, editable project with publication, author, country, keyword, and citation data.

If you try BibMedEd on a real topic, share what worked and what blocked you in [GitHub Discussions](https://github.com/ata381/BibMedEd/discussions). Useful feedback includes:

- the research field and approximate corpus size;
- the databases you normally search;
- the analysis or export you were trying to produce;
- the first confusing or missing step.

Do not post unpublished search data, credentials, or sensitive research material.

## Make a first contribution

The most direct contribution is a new bibliographic-source adapter. Each adapter expands the literature available to every user, and the registry auto-discovers new `BaseSourceAdapter` subclasses without a registration-file edit.

1. Choose an open task from [`GOOD_FIRST_ISSUES.md`](https://github.com/ata381/BibMedEd/blob/master/GOOD_FIRST_ISSUES.md).
2. Comment on the linked issue and ask to be assigned.
3. Follow the [contributing guide](https://github.com/ata381/BibMedEd/blob/master/CONTRIBUTING.md) and the [adapter walkthrough](adapters.md).
4. Open a focused PR with fixture-based tests and `Closes #N`.

Documentation, reproducible case studies, bug reports, and usability feedback are also welcome. Maintainers aim to acknowledge contribution questions and claims within three working days.

## Contributors

Recent community contributions added the command-line search workflow and improved its failure handling:

- [@BaygeldiAza](https://github.com/BaygeldiAza) contributed dry-run result estimates and the full CLI search pipeline ([#46](https://github.com/ata381/BibMedEd/pull/46), [#52](https://github.com/ata381/BibMedEd/pull/52)).
- [@landon-personal](https://github.com/landon-personal) contributed clean CLI handling for unknown sources and network failures ([#50](https://github.com/ata381/BibMedEd/pull/50)).

GitHub maintains the complete [contributors graph](https://github.com/ata381/BibMedEd/graphs/contributors).

## Stay involved

- Use [Discussions](https://github.com/ata381/BibMedEd/discussions) for questions, workflow feedback, and early ideas.
- Use [Issues](https://github.com/ata381/BibMedEd/issues) for reproducible bugs and scoped work.
- Read the public [roadmap](https://github.com/ata381/BibMedEd/blob/master/ROADMAP.md) and react to issues you care about.
- Cite BibMedEd through its [Zenodo concept DOI](https://doi.org/10.5281/zenodo.20404321), which resolves to the latest archived release.
