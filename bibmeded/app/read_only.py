"""Read-only public demo mode (``BIBMEDED_READ_ONLY=true``).

BibMedEd has no authentication, so a public instance is only safe when nothing
can be mutated and no request can fan out to external bibliographic APIs. The
middleware is an allowlist of safe HTTP methods rather than a list of blocked
routes, so endpoints added later are covered without anyone remembering to opt
them in. Request sessions are additionally bound to a dedicated engine whose
connections the database itself holds read-only, so a GET handler that writes
through any path (ORM flush, Core ``update()``, raw SQL, bulk helpers) fails.
"""

import json
import logging
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, event, make_url
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketClose

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
POSTGRES_READ_ONLY_OPTIONS = "-c default_transaction_read_only=on"
REASSERT_STATEMENTS = {
    "postgresql": "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY",
    "sqlite": "PRAGMA query_only = ON",
}
READ_ONLY_PROBES = {
    "postgresql": ("SHOW transaction_read_only", "on"),
    "sqlite": ("PRAGMA query_only", "1"),
}
WEBSOCKET_POLICY_VIOLATION = 1008
READ_ONLY_DETAIL = (
    "This BibMedEd instance is a read-only public demo. "
    "Install BibMedEd locally to create projects and run your own searches."
)


class ReadOnlyViolation(PermissionError):
    pass


def read_only_payload() -> dict[str, object]:
    return {"detail": READ_ONLY_DETAIL, "read_only": True}


class ReadOnlyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            logger.info("read-only mode rejected websocket %s", scope.get("path", ""))
            await WebSocketClose(code=WEBSOCKET_POLICY_VIOLATION, reason="read-only demo")(scope, receive, send)
            return
        if scope["type"] != "http" or scope["method"].upper() in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        logger.info("read-only mode rejected %s %s", scope["method"], scope.get("path", ""))
        body = json.dumps(read_only_payload()).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _reassert_on_checkout(statement: str) -> Callable[..., None]:
    # Re-applied on every pool checkout so a statement that lifts the guard
    # (``PRAGMA query_only = OFF``, ``SET SESSION CHARACTERISTICS ... READ
    # WRITE``) cannot outlive the request that issued it.
    def listener(dbapi_connection, connection_record, connection_proxy) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(statement)
        finally:
            cursor.close()
        dbapi_connection.commit()

    return listener


def _merged_postgres_options(url: URL) -> tuple[URL, str]:
    existing = url.query.get("options")
    if isinstance(existing, tuple):
        existing = " ".join(existing)
    options = f"{existing} {POSTGRES_READ_ONLY_OPTIONS}" if existing else POSTGRES_READ_ONLY_OPTIONS
    return url.difference_update_query(["options"]), options


def create_read_only_engine(url: str) -> Engine:
    parsed = make_url(url)
    backend = parsed.get_backend_name()
    if backend == "postgresql":
        stripped, options = _merged_postgres_options(parsed)
        engine = create_engine(stripped, connect_args={"options": options})
    elif backend == "sqlite":
        engine = create_engine(parsed, connect_args={"check_same_thread": False})
    else:
        raise RuntimeError(f"BIBMEDED_READ_ONLY has no database-level guard for {backend!r} databases")
    event.listen(engine, "checkout", _reassert_on_checkout(REASSERT_STATEMENTS[backend]))
    return engine


def verify_read_only_engine(engine: Engine) -> None:
    backend = engine.url.get_backend_name()
    probe, expected = READ_ONLY_PROBES[backend]
    with engine.connect() as connection:
        actual = connection.exec_driver_sql(probe).scalar()
    if str(actual).lower() != expected:
        raise RuntimeError(
            f"read-only database guard is not active: {probe!r} returned {actual!r}, expected {expected!r}"
        )
    logger.info("read-only database guard verified (%s -> %s)", probe, actual)


def _reject_flush(session: Session, flush_context, instances) -> None:
    raise ReadOnlyViolation(READ_ONLY_DETAIL)


def guard_session(session: Session) -> Session:
    if not event.contains(session, "before_flush", _reject_flush):
        event.listen(session, "before_flush", _reject_flush)
    return session


async def read_only_violation_handler(request: Request, exc: ReadOnlyViolation) -> JSONResponse:
    logger.warning("blocked database write during %s %s in read-only mode", request.method, request.url.path)
    return JSONResponse(status_code=403, content=read_only_payload())
