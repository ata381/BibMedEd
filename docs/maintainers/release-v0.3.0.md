# BibMedEd 0.3 launch kit

This is the maintainer-side checklist and copy deck for publishing BibMedEd 0.3. It is excluded from the public MkDocs build. Every networked action below requires an explicit maintainer go-ahead.

## Release sequence

The repository contains complete 0.2.0 metadata at commit `fa0e222`, but the corresponding Git tag and GitHub release were not published. Preserve that history before publishing 0.3.0:

1. Run the backend, frontend, documentation, and metadata checks on the 0.3.0 release commit.
2. Create annotated local tag `v0.2.0` at `fa0e222`.
3. With approval, push `v0.2.0` and publish the matching GitHub release so its changelog link and Zenodo archive resolve.
4. Push the reviewed 0.3.0 release commit.
5. Create annotated tag `v0.3.0` on that commit, push it, and publish the GitHub release using the 0.3.0 section of `CHANGELOG.md`.
6. Verify the GitHub Pages deployment, Zenodo version record, citation metadata, and release links.

Do not deploy the application itself as a public writable demo. BibMedEd has no built-in authentication. Use the workflow recording, screenshots, and bundled sample project until a deliberately read-only demo mode exists.

## Contributor discovery note

Post this on the most recent contribution thread after approval:

> Thanks again for contributing to BibMedEd. I am improving the path for new contributors and would value one bit of context: how did you discover the repository or issue, and what made it feel worth picking up? Even a one-sentence answer would help us make that path repeatable.

## GitHub Discussion draft

**Title:** BibMedEd 0.3: sample project, CLI search, Lens.org, and a call for research pilots

> BibMedEd 0.3 is ready. The release adds a network-free sample project, full command-line search, and Lens.org Scholarly as the fifth built-in source.
>
> The CLI work also marks an important community milestone. @BaygeldiAza contributed dry-run estimates and full search execution, while @landon-personal improved source and network error handling. Thank you both.
>
> We are looking for three medical-education researchers or academic librarians willing to try the sample workflow and tell us where it becomes confusing or incomplete. You do not need to share unpublished data; the bundled synthetic project is enough.
>
> Developers can also claim one of the focused adapter tasks in `GOOD_FIRST_ISSUES.md`. If you are interested, reply with either **research pilot** or **adapter**, and we will point you to the shortest next step.

## LinkedIn draft

> I have released BibMedEd 0.3, an open-source, self-hosted bibliometric analysis platform for medical-education research.
>
> This release is designed to make the project easier to evaluate before committing a real dataset: a bundled synthetic project now opens the complete analysis and export workflow without an API key or network request. It also adds Lens.org Scholarly and a full command-line search workflow.
>
> The CLI is BibMedEd's first substantial externally contributed feature. Thank you to Baygeldi (@BaygeldiAza) for the dry-run and full-search work, and Landon Kruse (@landon-personal) for improving failure handling.
>
> I am looking for three medical-education researchers or academic librarians to try the sample workflow and give candid feedback. I am especially interested in the first confusing step, missing database, or export that would stop you using it in a real study.
>
> Project and workflow tour: https://ata381.github.io/BibMedEd/whats-new/

Only tag contributors on a social platform if they use that platform and are comfortable being tagged.

## Research-pilot outreach draft

**Subject:** Would you test a reproducible bibliometrics workflow on a synthetic project?

> Hi [name],
>
> I maintain BibMedEd, an open-source tool for multi-source bibliographic search, deduplication, bibliometric analysis, network visualisation, and PRISMA-oriented methodology export.
>
> I am looking for a small number of medical-education researchers or academic librarians to test a bundled synthetic project. It takes roughly 15 minutes, requires no unpublished data, and I am not asking for an endorsement. The useful outcome is simply learning the first point where the workflow is confusing, incomplete, or unsuitable for a real study.
>
> If that fits your work, the overview is here: https://ata381.github.io/BibMedEd/whats-new/
>
> Thanks,
> Ata

Personalize the first paragraph with the recipient's published methods work. Do not send bulk or unsolicited repetitive messages.

## Time-sensitive AMEE option

AMEE 2026 runs from 22–26 August 2026. If the release is published during the conference and the maintainer already participates in an appropriate AMEE space, share the sample-workflow request as a methods-feedback invitation. Do not join unrelated threads solely to drop a project link.

## Thirty-day measures

Measure adoption before popularity:

- three external researchers or librarians complete the sample workflow;
- one team evaluates BibMedEd against a real research question;
- two substantive Discussion threads from non-maintainers;
- two external issues or pull requests;
- one independent case study, testimonial, or methods citation;
- ten stars as a secondary discovery indicator.

Record how every participant discovered the project. GitHub clone counts include CI and automated checkouts, so they are not a reliable adoption measure by themselves.

## Approval gates

- [ ] Push the release-preparation commit
- [ ] Push the historical `v0.2.0` tag and publish its GitHub release
- [ ] Push `v0.3.0` and publish its GitHub release
- [ ] Post the GitHub Discussion
- [ ] Post on LinkedIn or another social account
- [ ] Send contributor-discovery notes
- [ ] Send individually personalized pilot invitations
