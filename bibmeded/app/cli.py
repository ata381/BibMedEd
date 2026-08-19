import argparse
import asyncio
import sys
from collections.abc import Sequence

import httpx

from app.adapters.registry import get_adapter


async def _dry_run_search(query: str, source: str) -> int:
    try:
        adapter = get_adapter(source)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    try:
        result = await adapter.search(query)
        print(f"Estimated results: {result.total_count}")
    except httpx.HTTPError as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await adapter.close()

    return 0


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

    args = parser.parse_args(argv)

    if args.command == "search":
        if not args.dry_run:
            parser.error("search currently requires --dry-run")

        return asyncio.run(
            _dry_run_search(
                query=args.query,
                source=args.source,
            )
        )

    return 1
