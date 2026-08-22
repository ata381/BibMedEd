import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
import httpx
from lxml import etree
import time
from app.adapters.registry import get_adapter
from app.database import SessionLocal
from app.models import QueryStatus, SearchProject, SearchQuery
from app.workers.tasks import run_search


async def _dry_run_search(query: str, source: str) -> int:
    try:
        adapter = get_adapter(source)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    try:
        result = await adapter.search(query)
        print(f"Estimated results: {result.total_count}")
    except (httpx.HTTPError, json.JSONDecodeError, etree.XMLSyntaxError) as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await adapter.close()

    return 0


def _validate_source(source: str) -> bool:
    try:
        get_adapter(source)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return False

    return True


def _run_search(
            query: str,
            source: str,
            year_start: str | None,
            year_end: str | None,
            max_results: int
        ) -> int:
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
                print(
                    f"Completed: {search_query.result_count or 0} records"
                )
                return 0

            if search_query.status == QueryStatus.failed:
                print(
                    "Search failed",
                    file=sys.stderr,
                )
                return 1



            print(
                f"Status: {search_query.status.value}",
                file=sys.stderr,
            )

            time.sleep(2)

    finally:
        db.close()

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bibmeded")

    subparsers = parser.add_subparsers(dest="command", required=True)

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
