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

- The BibMedEd FastAPI backend (`bibmeded/app/`)
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
