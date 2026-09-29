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

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, event, make_url
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketClose

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
POSTGRES_READ_ONLY_OPTIONS = "-c default_transaction_read_only=on"
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


def _sqlite_query_only(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA query_only = ON")
    finally:
        cursor.close()


def create_read_only_engine(url: str) -> Engine:
    backend = make_url(url).get_backend_name()
    if backend == "postgresql":
        return create_engine(url, connect_args={"options": POSTGRES_READ_ONLY_OPTIONS})
    if backend == "sqlite":
        engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(engine, "connect", _sqlite_query_only)
        return engine
    raise RuntimeError(f"BIBMEDED_READ_ONLY has no database-level guard for {backend!r} databases")


def _reject_flush(session: Session, flush_context, instances) -> None:
    raise ReadOnlyViolation(READ_ONLY_DETAIL)


def guard_session(session: Session) -> Session:
    if not event.contains(session, "before_flush", _reject_flush):
        event.listen(session, "before_flush", _reject_flush)
    return session


async def read_only_violation_handler(request: Request, exc: ReadOnlyViolation) -> JSONResponse:
    logger.warning("blocked database write during %s %s in read-only mode", request.method, request.url.path)
    return JSONResponse(status_code=403, content=read_only_payload())
