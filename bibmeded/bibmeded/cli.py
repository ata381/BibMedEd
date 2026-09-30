import argparse
import asyncio
import json
import sys
import time
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

import httpx
from lxml import etree

from bibmeded.adapters.registry import get_adapter, list_adapters
from bibmeded.adapters.settings import (
    adapter_configuration_error,
    adapter_kwargs,
    required_setting_env_var,
)
from bibmeded.models import QueryStatus, SearchProject, SearchQuery


def _collect_sources() -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for adapter in list_adapters():
        name = adapter["name"]
        kwargs = adapter_kwargs(name)
        requires_key = bool(adapter.get("requires_api_key"))
        if requires_key:
            api_key_mode = "required"
        elif "api_key" in kwargs:
            api_key_mode = "optional"
        else:
            api_key_mode = "no"

        config_error = adapter_configuration_error(name)
        has_key = bool(str(kwargs.get("api_key") or "").strip())
        if config_error:
            env_var = required_setting_env_var(name)
            status = f"missing {env_var}" if env_var else config_error
        elif requires_key and not has_key:
            status = "missing API key"
        elif has_key:
            status = "ready (key configured)"
        else:
            status = "ready"

        sources.append(
            {
                "name": name,
                "display_name": adapter["display_name"],
                "api_key_requirement": api_key_mode,
                "status": status,
            }
        )
    return sources


def _list_sources(as_json: bool = False) -> int:
    sources = _collect_sources()
    if as_json:
        print(json.dumps(sources, indent=2))
        return 0

    columns = (
        ("name", "NAME"),
        ("display_name", "DISPLAY NAME"),
        ("api_key_requirement", "API KEY"),
        ("status", "STATUS"),
    )
    widths = {
        key: max(len(header), *(len(row[key]) for row in sources)) if sources else len(header)
        for key, header in columns[:-1]
    }

    header_line = "   ".join(
        [*(header.ljust(widths[key]) for key, header in columns[:-1]), columns[-1][1]]
    )
    print(header_line)

    for row in sources:
        line = "   ".join(
            [*(row[key].ljust(widths[key]) for key, _ in columns[:-1]), row["status"]]
        )
        print(line)

    return 0

SERVER_MODULES = frozenset({"celery", "kombu", "billiard", "redis", "psycopg2"})


def _is_missing_server_module(exc: ModuleNotFoundError) -> bool:
    return exc.name is not None and exc.name.split(".")[0] in SERVER_MODULES


SERVER_EXTRA_HINT = (
    "Fetching records needs the task worker stack. "
    'Install it with: pip install "bibmeded[server]" (or use docker compose). '
    "`--dry-run` works without it."
)


async def _dry_run_search(query: str, source: str) -> int:
    configuration_error = adapter_configuration_error(source)
    if configuration_error:
        print(configuration_error, file=sys.stderr)
        return 1

    try:
        adapter = get_adapter(source, **adapter_kwargs(source))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    try:
        result = await adapter.search(query)
        print(f"Estimated results: {result.total_count}")
    except (httpx.HTTPError, json.JSONDecodeError, etree.XMLSyntaxError, ValueError) as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await adapter.close()

    return 0


def _validate_source(source: str) -> bool:
    configuration_error = adapter_configuration_error(source)
    if configuration_error:
        print(configuration_error, file=sys.stderr)
        return False

    try:
        adapter = get_adapter(source, **adapter_kwargs(source))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return False

    asyncio.run(adapter.close())
    return True


def _run_search(
    query: str,
    source: str,
    year_start: str | None,
    year_end: str | None,
    max_results: int,
) -> int:
    # Deferred so the CLI works without the bibmeded[server] extra.
    try:
        from bibmeded.database import SessionLocal
        from bibmeded.workers.tasks import run_search
    except ModuleNotFoundError as exc:
        if not _is_missing_server_module(exc):
            raise
        print(SERVER_EXTRA_HINT, file=sys.stderr)
        return 1

    if not _validate_source(source):
        return 1

    db = SessionLocal()

    try:
        project = SearchProject(
            name=f"CLI search: {query[:80]}",
        )

        db.add(project)
        db.commit()
        db.refresh(project)

        search_query = SearchQuery(
            project_id=project.id,
            query_string=query,
            database=source,
        )

        db.add(search_query)
        db.commit()
        db.refresh(search_query)

        print(
            f"Search started (query_id={search_query.id})",
            file=sys.stderr,
        )

        try:
            run_search.delay(
                search_query.id,
                source,
                year_start,
                year_end,
                max_results,
            )
        except Exception as exc:
            search_query.status = QueryStatus.failed
            db.commit()

            print(
                f"Could not start search: {exc}",
                file=sys.stderr
            )
            return 1

        print("Waiting for completion...", file=sys.stderr)

        start_time = time.time()
        timeout_seconds = 600

        while True:
            if time.time() - start_time > timeout_seconds:
                print("Search timed out. Check worker logs", file=sys.stderr)
                return 1

            db.refresh(search_query)

            if search_query.status == QueryStatus.completed:
                print(f"Completed: {search_query.result_count or 0} records")
                return 0

            if search_query.status == QueryStatus.failed:
                print("Search failed", file=sys.stderr)
                return 1

            print(
                f"Status: {search_query.status.value}",
                file=sys.stderr,
            )

            time.sleep(2)

    finally:
        db.close()


def _package_version() -> str:
    try:
        return version("bibmeded")
    except PackageNotFoundError:
        return "unknown"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bibmeded")

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    sources_parser = subparsers.add_parser(
        "sources",
        help="List available bibliographic sources and configuration status",
    )

    sources_parser.add_argument(
        "--json",
        action="store_true",
        help="Output sources as JSON",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Search a bibliographic source",
    )

    search_parser.add_argument(
        "query",
        help="Search query",
    )

    search_parser.add_argument(
        "--source",
        default="pubmed",
        help="Bibliographic source (default: pubmed)",
    )

    search_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate result count without fetching records",
    )

    search_parser.add_argument(
        "--year-start",
        help="Start publication year",
    )

    search_parser.add_argument(
        "--year-end",
        help="End publication year",
    )

    search_parser.add_argument(
        "--max-results",
        type=int,
        default=2000,
        help="Maximum number of results to fetch",
    )

    args = parser.parse_args(argv)

    if args.command == "sources":
        return _list_sources(as_json=args.json)

    if args.command == "search":
        if args.dry_run:
            return asyncio.run(
                _dry_run_search(
                    query=args.query,
                    source=args.source,
                )
            )

        return _run_search(
            query=args.query,
            source=args.source,
            year_start=args.year_start,
            year_end=args.year_end,
            max_results=args.max_results,
        )

    return 1
