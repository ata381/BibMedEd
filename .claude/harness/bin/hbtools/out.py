"""Every tool prints one JSON object with the same shape and exits 0 (done), 1 (refused), 2 (error)."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field

DONE, REFUSED, ERROR = 0, 1, 2


@dataclass
class Report:
    status: str  # done | refused | error | dry-run
    summary: str
    next_actions: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def exit_code(self) -> int:
        return {"done": DONE, "dry-run": DONE, "refused": REFUSED}.get(self.status, ERROR)


def emit(report: Report) -> int:
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    return report.exit_code()


def done(summary: str, **kw) -> Report:
    return Report("done", summary, **kw)


def refused(summary: str, **kw) -> Report:
    return Report("refused", summary, **kw)


def error(summary: str, **kw) -> Report:
    return Report("error", summary, **kw)


def dry_run(summary: str, **kw) -> Report:
    return Report("dry-run", summary, **kw)


def fail(summary: str) -> int:
    return emit(error(summary))


def eprint(*parts) -> None:
    print(*parts, file=sys.stderr)
