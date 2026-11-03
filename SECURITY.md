# Security Policy

## Supported versions

BibMedEd is pre-1.0. Only the current `master` branch receives security fixes.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security problems.**

Use GitHub's private vulnerability reporting:

1. Go to <https://github.com/ata381/BibMedEd/security/advisories/new>
2. Describe the vulnerability with reproduction steps and the impact you observed.
3. We will acknowledge within 5 business days and aim to publish a fix or mitigation within 30 days for high-severity issues.

If GitHub advisories are unavailable to you, you may file a regular issue containing only the line "Security report — please contact me privately" and a maintainer will reach out.

## Scope

In scope:

- The BibMedEd FastAPI backend (`bibmeded/bibmeded/`)
- The Celery worker pipeline
- The Next.js frontend (`bibmeded/frontend/`)
- The provided Docker images and `render.yaml` deployment blueprint
- Adapter implementations shipped in this repo

Out of scope:

- Vulnerabilities in upstream APIs (PubMed, OpenAlex) — report those to NCBI / OpenAlex directly.
- Issues that require an attacker to already control the host running BibMedEd.
- Rate-limit bypass or abuse of free upstream APIs.

## Hall of fame

Researchers who responsibly disclose valid issues will be credited (with consent) in release notes and the advisory.

## Dependency advisory assessments

### GHSA-g3hv-75wg-m249 (reviewed 2026-11-04)

The frontend overrides minimatch 10.x to patched 11.0.4 or later. This covers the
copy used by typescript-eslint, which contained the affected preprocessing code.

The remaining minimatch 3.1.5 copy is a development dependency of ESLint and its
plugins. Its source has neither `firstPhasePreProcess`, `secondPhasePreProcess`
nor the `optimizationLevel` preprocessing path described in the
[upstream advisory](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249).
The advisory database's `<11.0.1` range therefore overmatches this legacy copy.
The legacy-version alert is assessed as inaccurate for this specific advisory;
this is not a blanket exemption for other minimatch vulnerabilities. Keep its
compatible callable API until the parent packages migrate. Reassess if the
resolved major version or advisory scope changes. npm audit may continue to
report this advisory and its dependent packages despite this assessment.

The same audit also found GHSA-mrhx-c7xc-m3w5 in development-only Zod 4.6.5;
the lockfile updates it to patched 4.6.7 within the parent's existing range.
