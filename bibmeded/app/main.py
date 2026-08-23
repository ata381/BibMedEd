import contextvars
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import projects, search, publications, analysis, export, adapters

# Per-request id propagated to every log line emitted during the request. The
# search dispatch route (app/routers/search.py) reads this value and forwards
# it as an explicit `request_id` argument to `run_search.delay(...)`, so the
# Celery task can bind the same id onto its own log records and methodology
# steps — giving an SRE one id to grep across the API -> worker -> DB path.
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def _configure_logging() -> None:
    """Configure root logger once. Format includes request_id so logs are correlatable."""
    if logging.getLogger().handlers:
        return  # already configured (avoid double-attaching in tests / reload)
    handler = logging.StreamHandler()
    fmt = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(_RequestIdFilter())
    root = logging.getLogger()
    root.setLevel(os.environ.get("BIBMEDED_LOG_LEVEL", "INFO").upper())
    root.addHandler(handler)


_configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="BibMedEd",
        description=(
            "Bibliometric Analysis Platform for Medical Education.\n\n"
            "**Programmatic access**: this is the auto-generated OpenAPI surface. "
            "Interactive Swagger UI lives at [`/docs`](/docs), ReDoc at [`/redoc`](/redoc), "
            "and the raw spec at [`/openapi.json`](/openapi.json) for client codegen. "
            "Analysis responses are stamped with a `schema_version` field so downstream "
            "pipelines can pin against a known shape. See "
            "[`docs/scripting.md`](https://github.com/ata381/BibMedEd/blob/master/docs/scripting.md) "
            "for an end-to-end Jupyter-notebook example."
        ),
        version="0.3.0",
        contact={"name": "BibMedEd", "url": "https://github.com/ata381/BibMedEd"},
        license_info={"name": "MIT", "url": "https://github.com/ata381/BibMedEd/blob/master/LICENSE"},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "%s %s -> %s in %.1fms",
                request.method,
                request.url.path,
                getattr(locals().get("response", None), "status_code", "ERR"),
                elapsed_ms,
            )
            request_id_ctx.reset(token)
        response.headers["x-request-id"] = rid
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # exc_info=True propagates the full traceback to the log, including the
        # bibmeded module the failure originated in — production tracebacks point
        # at the real failure site rather than the handler.
        logger.exception(
            "Unhandled error on %s %s?%s: %s",
            request.method, request.url.path, request.url.query, type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id_ctx.get(),
            },
        )

    app.include_router(projects.router)
    app.include_router(search.router)
    app.include_router(publications.router)
    app.include_router(analysis.router)
    app.include_router(export.router)
    app.include_router(adapters.router)

    @app.get("/api/health")
    def health_check():
        # Backwards-compatible shallow check kept for any external monitors already
        # pointing here. New deploys should target /api/live + /api/ready.
        return {"status": "ok"}

    @app.get("/api/live")
    def liveness():
        """Liveness probe — confirms the process is up. No I/O, never fails."""
        return {"status": "alive"}

    @app.get("/api/ready")
    def readiness():
        """Readiness probe — pings DB and Redis. Returns 503 if either is unreachable."""
        from sqlalchemy import text
        from app.database import SessionLocal

        checks: dict[str, str] = {}
        all_ok = True

        try:
            sess = SessionLocal()
            try:
                sess.execute(text("SELECT 1"))
                checks["db"] = "ok"
            finally:
                sess.close()
        except Exception as exc:
            checks["db"] = f"error: {type(exc).__name__}"
            all_ok = False

        try:
            import redis as redis_lib  # imported lazily so test environments
            client = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
            client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {type(exc).__name__}"
            all_ok = False

        payload = {"status": "ready" if all_ok else "not_ready", "checks": checks}
        if not all_ok:
            return JSONResponse(status_code=503, content=payload)
        return payload

    return app


app = create_app()
