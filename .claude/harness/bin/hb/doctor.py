"""doctor: can this run act at all? Identity, auth, pause state, tool facts, network reachability."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import config, gh, issues

PAUSE_FILE = Path(".claude/harness/PAUSE")
PROBE_HOSTS = ("https://api.github.com", "https://pypi.org", "https://pypistats.org", "https://api.openalex.org")


def _probe(url: str) -> str:
    try:
        proc = subprocess.run(["curl", "-sS", "-o", os.devnull, "-w", "%{http_code}", "--max-time", "8", url],
                              capture_output=True, text=True)
        return proc.stdout.strip() or f"error: {proc.stderr.strip()[:80]}"
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return f"error: {exc}"


def run(expected_login: str | None, probe_network: bool) -> dict:
    facts: dict = {"python": sys.version.split()[0], "cwd": os.getcwd()}
    stops: list[str] = []

    auth = gh.run(["auth", "status"], check=False)
    facts["gh_auth"] = "ok" if auth.rc == 0 else "not authenticated"
    if auth.rc != 0:
        stops.append("gh is not authenticated: " + (auth.stderr or auth.stdout).strip()[:200])
    version = gh.run(["--version"], check=False)
    facts["gh_version"] = (version.stdout or "").splitlines()[0] if version.rc == 0 else "missing"

    login = None
    if auth.rc == 0:
        who = gh.run(["api", "user", "--jq", ".login"], check=False)
        login = who.stdout.strip() if who.rc == 0 else None
        facts["identity"] = login
        if expected_login and login != expected_login:
            stops.append(f"gh identity is {login!r}, expected {expected_login!r}")
        limit = gh.run(["api", "rate_limit", "--jq", ".resources.core.remaining"], check=False)
        facts["rate_limit_remaining"] = limit.stdout.strip() if limit.rc == 0 else None

    facts["pause_file"] = PAUSE_FILE.exists()
    if facts["pause_file"]:
        stops.append("PAUSE file present on master")

    if auth.rc == 0:
        try:
            cmds = issues.owner_commands(None)
            last_toggle = next((c for c in reversed(cmds) if c["command"] in ("pause", "resume")), None)
            facts["last_owner_toggle"] = last_toggle
            if last_toggle and last_toggle["command"] == "pause":
                stops.append(f"owner posted /pause at {last_toggle['at']}")
        except gh.GhError as exc:
            facts["last_owner_toggle"] = f"unreadable: {exc}"

    if probe_network:
        facts["network"] = {url: _probe(url) for url in PROBE_HOSTS}

    return {"stop": bool(stops), "stops": stops, "facts": facts}
