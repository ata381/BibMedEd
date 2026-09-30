import contextvars

# Per-request id propagated to every log line emitted during the request. The
# search dispatch route (bibmeded/routers/search.py) reads this value and forwards
# it as an explicit `request_id` argument to `run_search.delay(...)`, so the
# Celery task can bind the same id onto its own log records and methodology
# steps — giving an SRE one id to grep across the API -> worker -> DB path.
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
