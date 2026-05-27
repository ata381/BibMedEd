"""Liveness + readiness probe tests.

`/api/live` must return 200 even when dependencies are dead — its only job is
"is the process running". `/api/ready` pings DB and Redis and is allowed to
return 503 when either fails.
"""

from unittest.mock import patch


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
