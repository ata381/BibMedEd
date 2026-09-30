"""Glob matching for repo paths with ** semantics (fnmatch treats * and ** alike, which is wrong here)."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern:
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, pattern: str) -> bool:
    return bool(_compile(pattern).match(path))


def first_match(path: str, patterns: Iterable[str]) -> str | None:
    for pattern in patterns:
        if matches(path, pattern):
            return pattern
    return None


def hits(paths: Iterable[str], patterns: Iterable[str]) -> list[tuple[str, str]]:
    patterns = tuple(patterns)
    found = []
    for path in paths:
        pattern = first_match(path, patterns)
        if pattern:
            found.append((path, pattern))
    return found


def all_within(paths: Iterable[str], patterns: Iterable[str]) -> list[str]:
    """Return the paths that are NOT covered by any pattern (empty list means all within)."""
    patterns = tuple(patterns)
    return [p for p in paths if first_match(p, patterns) is None]
