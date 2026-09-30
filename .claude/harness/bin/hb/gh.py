"""Thin wrapper around the gh CLI. Tests replace RUNNER with a fake."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence


class GhError(RuntimeError):
    def __init__(self, args: Sequence[str], rc: int, stderr: str):
        super().__init__(f"gh {' '.join(args)} failed ({rc}): {stderr.strip()[:500]}")
        self.args_list = list(args)
        self.rc = rc
        self.stderr = stderr


@dataclass
class Result:
    rc: int
    stdout: str
    stderr: str


def _subprocess_runner(args: Sequence[str], stdin: str | None) -> Result:
    proc = subprocess.run(
        ["gh", *args], input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return Result(proc.returncode, proc.stdout, proc.stderr)


RUNNER: Callable[[Sequence[str], str | None], Result] = _subprocess_runner


def run(args: Sequence[str], stdin: str | None = None, check: bool = True) -> Result:
    res = RUNNER(list(args), stdin)
    if check and res.rc != 0:
        raise GhError(args, res.rc, res.stderr)
    return res


def run_json(args: Sequence[str], stdin: str | None = None):
    res = run(args, stdin)
    text = res.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GhError(args, 0, f"non-JSON output: {text[:200]}") from exc


def api(path: str, *, method: str = "GET", fields: dict | None = None, raw_input: str | None = None, paginate: bool = False):
    args = ["api", path]
    if method != "GET":
        args += ["-X", method]
    if paginate:
        args.append("--paginate")
    if raw_input is not None:
        args += ["--input", "-"]
        return run_json(args, stdin=raw_input)
    for key, value in (fields or {}).items():
        args += ["-f", f"{key}={value}"]
    return run_json(args)


def graphql(query: str, variables: dict | None = None):
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in (variables or {}).items():
        flag = "-F" if isinstance(value, (int, bool)) else "-f"
        args += [flag, f"{key}={value}"]
    return run_json(args)
