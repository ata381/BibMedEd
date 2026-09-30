"""Static policy for the harness tools. This file is a protected path: changing it changes what the agents may do."""

from __future__ import annotations

REPO = "ata381/BibMedEd"
OWNER = "ata381"
DEVELOPERS = frozenset({"MugeBakiryol"})
TRUSTED = frozenset({OWNER, *DEVELOPERS})
DEPENDABOT = "dependabot[bot]"
CODEX_LOGIN = "chatgpt-codex-connector"
AGENT_BRANCH_PREFIX = "claude/"
ROLES = ("maintainer", "worker")

INBOX_ISSUE = 102
STATE_MARKER = "<!-- agent-state -->"
FOOTER = (
    "<sub>— BibMedEd maintainer agent (automated). A human maintainer reviews this repo too; "
    "reply here if something looks wrong.</sub>"
)
MARKER_RE = r"<!--\s*bibmeded-(maintainer|worker|cloud-manager)(?:\s+sha=([0-9a-f]{7,40}))?\s*-->"
HEARTBEAT_PREFIX = "Last run:"

CODEX_GRACE_HOURS = 3
AGENT_LATER_RUN_HOURS = 3
DEPENDABOT_COOLDOWN_DAYS = 7
FLOOD_MAX_NEW_PRS = 5
FLOOD_MAX_NEW_ISSUES = 10
CLOSE_CAP_PER_RUN = 3

REQUIRED_CHECKS = (
    "Backend tests (Python 3.12)",
    "Backend tests (Python 3.13)",
    "Frontend build",
    "Docs build (MkDocs strict)",
    "Docker build smoke test",
)
FRONTEND_EXTRA_CHECK = "E2E accessibility (Chromium)"
FRONTEND_PREFIX = "bibmeded/frontend/"

# Paths that execute in CI, at install, at build, in Docker, in the docs build or under pytest,
# plus every file an agent reads as instructions. Any change here in an outside PR is CRITICAL.
CRITICAL_PATHS = (
    ".github/**",
    "**/.claude/**",
    "**/CLAUDE.md",
    "**/CLAUDE.local.md",
    "**/AGENTS.md",
    ".mcp.json",
    "CONTRIBUTING.md",
    "GOOD_FIRST_ISSUES.md",
    "SECURITY.md",
    "mkdocs.yml",
    "docs/javascripts/**",
    "bibmeded/pyproject.toml",
    "**/setup.py",
    "**/setup.cfg",
    "**/pytest.ini",
    "**/tox.ini",
    "**/conftest.py",
    "**/sitecustomize.py",
    "**/*.pth",
    "bibmeded/scripts/**",
    "bibmeded/alembic/**",
    "bibmeded/alembic.ini",
    "**/Dockerfile",
    "**/docker-compose*",
    "render.yaml",
    "bibmeded/frontend/package.json",
    "bibmeded/frontend/package-lock.json",
    "bibmeded/frontend/next.config.*",
    "bibmeded/frontend/playwright.config.*",
    "bibmeded/frontend/eslint.config.*",
    "bibmeded/frontend/postcss.config.*",
    "bibmeded/frontend/tsconfig.json",
    "bibmeded/frontend/e2e/**",
    "**/.npmrc",
    "**/.pre-commit-config.yaml",
)

# Never merged by an agent, whoever the author is. The owner merges these.
NEVER_MERGE_PATHS = (
    ".github/**",
    "**/.claude/**",
    "**/CLAUDE.md",
    "**/CLAUDE.local.md",
    "**/AGENTS.md",
    ".mcp.json",
    "CONTRIBUTING.md",
    "GOOD_FIRST_ISSUES.md",
    "SECURITY.md",
    "LICENSE",
    "CITATION.cff",
    ".zenodo.json",
    "paper.md",
    "paper.bib",
    "render.yaml",
    "bibmeded/bibmeded/read_only.py",
    "bibmeded/alembic/**",
)
# Exceptions to NEVER_MERGE for the maintainer's own release-prep PR and dependabot action bumps.
RELEASE_PREP_ALLOWED = (
    "bibmeded/pyproject.toml",
    "bibmeded/bibmeded/main.py",
    "CITATION.cff",
    "CHANGELOG.md",
    "docs/whats-new.md",
    "ROADMAP.md",
    "README.md",
)
DEPENDABOT_WORKFLOW_BUMP_PREFIX = "chore(ci)"
NEEDS_OWNER_TITLE_PREFIX = "needs-owner:"
# Dependency manifests: changed only by dependabot or, for the version line, the release-prep PR.
DEPENDENCY_MANIFESTS = (
    "bibmeded/pyproject.toml",
    "bibmeded/frontend/package.json",
    "bibmeded/frontend/package-lock.json",
)

# Worker PRs during the sprint may only touch these without a human approval.
WORKER_ALLOWLIST = (
    "bibmeded/tests/**",
    "bibmeded/bibmeded/adapters/**",
    "bibmeded/bibmeded/analysis/**",
    "bibmeded/bibmeded/services/**",
    "docs/**",
    "README.md",
    "CHANGELOG.md",
    "GOOD_FIRST_ISSUES.md",
    "ROADMAP.md",
    "mkdocs.yml",
)
WORKER_ALLOWLIST_UNTIL = "2026-10-31"

ESCALATION_KINDS = (
    "decision", "security", "release", "held-ci", "protected-path", "dependency", "ci", "state", "other",
)
ESCALATION_STATUSES = ("open", "approved", "rejected", "done")
VERDICTS = ("CLEARED", "CLEARED-WITH-NOTES", "HOLD", "REJECT-SUSPICIOUS")
RELEASE_STATES = ("idle", "prep-open", "merged-untagged", "awaiting-pypi", "published")
MODES = ("normal", "paused", "triage-only")
METRICS_WEEKS_KEPT = 8
