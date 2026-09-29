"""Read-only public demo mode (``BIBMEDED_READ_ONLY=true``).

BibMedEd has no authentication, so a public instance is only safe when nothing
can be mutated and no request can fan out to external bibliographic APIs. The
middleware is an allowlist of safe HTTP methods rather than a list of blocked
routes, so endpoints added later are covered without anyone remembering to opt
them in. The session guard is a second line of defence for GET handlers that
would otherwise write to the database.
"""

import json
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import event
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
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


def _reject_flush(session: Session, flush_context, instances) -> None:
    raise ReadOnlyViolation(READ_ONLY_DETAIL)


def guard_session(session: Session) -> Session:
    if not event.contains(session, "before_flush", _reject_flush):
        event.listen(session, "before_flush", _reject_flush)
    return session


async def read_only_violation_handler(request: Request, exc: ReadOnlyViolation) -> JSONResponse:
    logger.warning("blocked database write during %s %s in read-only mode", request.method, request.url.path)
    return JSONResponse(status_code=403, content=read_only_payload())
