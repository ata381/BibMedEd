"""Liveness + readiness probe tests.

`/api/live` must return 200 even when dependencies are dead — its only job is
"is the process running". `/api/ready` pings DB and Redis and is allowed to
return 503 when either fails.
"""

import logging
import re
from unittest.mock import patch

import pytest

GENERATED_REQUEST_ID = re.compile(r"[0-9a-f]{12}")


def test_liveness_returns_alive(client):
    resp = client.get("/api/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


def test_legacy_health_endpoint_still_works(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readiness_passes_when_dependencies_ok(client):
    """In the test environment, Redis is unreachable but the DB SELECT 1 will work.
    Patch the redis ping so it succeeds and confirm a 200 ready response."""

    class _OkRedis:
        def ping(self):
            return True

    with patch("redis.from_url", return_value=_OkRedis()):
        resp = client.get("/api/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["redis"] == "ok"


def test_readiness_returns_503_when_redis_down(client):
    """If Redis is unreachable, /ready returns 503 with the specific failing check."""

    def _bad_redis(*_a, **_k):
        raise ConnectionError("redis unreachable")

    with patch("redis.from_url", side_effect=_bad_redis):
        resp = client.get("/api/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["db"] == "ok"
    assert "error" in body["checks"]["redis"]


def test_request_id_round_trips(client):
    """Custom request id header should round-trip back in the response."""
    resp = client.get("/api/live", headers={"X-Request-ID": "test-rid-abc"})
    assert resp.headers.get("x-request-id") == "test-rid-abc"


def test_request_id_generated_when_missing(client):
    """If the client doesn't send X-Request-ID, the server generates one."""
    resp = client.get("/api/live")
    rid = resp.headers.get("x-request-id")
    assert rid is not None and len(rid) >= 8


@pytest.mark.parametrize("rid", ["a", "corr-id-999", "trace_1.span-2", "A" * 64])
def test_request_id_with_allowed_characters_round_trips(client, rid):
    resp = client.get("/api/live", headers={"X-Request-ID": rid})
    assert resp.headers.get("x-request-id") == rid


@pytest.mark.parametrize(
    "rid",
    ["abc def", "abc;drop", "abc=1,def=2", "A" * 65, "x" * 5000],
    ids=["space", "semicolon", "comma-equals", "over-length", "huge"],
)
def test_unsafe_request_id_is_replaced_with_generated_one(client, rid):
    resp = client.get("/api/live", headers={"X-Request-ID": rid})
    returned = resp.headers.get("x-request-id")
    assert returned != rid
    assert GENERATED_REQUEST_ID.fullmatch(returned)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "abc\r\nINFO [forged] bibmeded: injected",
        "abc\n",
        "abc\r",
        "abc\x00",
        "abc\tdef",
        "abc def",
        "abç",
        "A" * 65,
    ],
)
def test_client_request_id_rejects_values_that_could_forge_log_lines(raw):
    from bibmeded.main import _client_request_id

    assert _client_request_id(raw) is None


def test_client_request_id_accepts_conservative_token():
    from bibmeded.main import _client_request_id

    assert _client_request_id("corr-id-999") == "corr-id-999"
    assert _client_request_id("A" * 64) == "A" * 64


def test_log_records_carry_sanitised_request_id(client, caplog):
    from bibmeded.main import _RequestIdFilter

    injected = "abc INFO [forged] bibmeded.main: injected"
    request_id_filter = _RequestIdFilter()
    caplog.handler.addFilter(request_id_filter)
    try:
        with caplog.at_level(logging.INFO, logger="bibmeded.main"):
            resp = client.get("/api/live", headers={"X-Request-ID": injected})
    finally:
        caplog.handler.removeFilter(request_id_filter)

    returned = resp.headers.get("x-request-id")
    assert GENERATED_REQUEST_ID.fullmatch(returned)
    request_records = [r for r in caplog.records if r.name == "bibmeded.main" and "/api/live" in r.getMessage()]
    assert request_records
    for record in request_records:
        assert record.request_id == returned
        assert "forged" not in record.request_id
        assert "forged" not in record.getMessage()
