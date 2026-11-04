import asyncio
import multiprocessing
import os
import time
from unittest.mock import AsyncMock

import pytest

from bibmeded.services.pubmed import PubMedClient
from bibmeded.services.pubmed_rate_limit import RedisPubMedLimiter


async def test_shared_limiter_retries_until_redis_grants_slot(monkeypatch):
    limiter = RedisPubMedLimiter("redis://localhost", "fixture-key", 3)
    limiter._redis.eval = AsyncMock(side_effect=[334, 1, 0])
    sleep = AsyncMock()
    monkeypatch.setattr("bibmeded.services.pubmed_rate_limit.asyncio.sleep", sleep)
    try:
        await limiter.acquire()
        assert limiter.interval_ms == 334
        assert [call.args[0] for call in sleep.call_args_list] == [0.334, 0.001]
        assert "fixture-key" not in limiter.bucket
        assert limiter._redis.eval.await_count == 3
    finally:
        await limiter.close()


async def test_redis_failure_prevents_upstream_request():
    async with PubMedClient(redis_url="redis://localhost") as client:
        client._shared_limiter.acquire = AsyncMock(side_effect=ConnectionError("unavailable"))
        client._client.get = AsyncMock()
        with pytest.raises(ConnectionError):
            await client.search("fixture")
        client._client.get.assert_not_called()


async def test_search_and_fetch_share_one_limiter():
    from pathlib import Path
    from unittest.mock import Mock
    async with PubMedClient(redis_url="redis://localhost") as client:
        client._shared_limiter.acquire = AsyncMock()
        client._client.get = AsyncMock(side_effect=[
            Mock(text=Path("tests/fixtures/pubmed_search_response.xml").read_text()),
            Mock(text=Path("tests/fixtures/pubmed_response.xml").read_text()),
        ])
        await client.search("fixture")
        await client.fetch(["38000001"])
        assert client._shared_limiter.acquire.await_count == 2


def test_key_buckets_are_stable_normalized_and_distinct():
    limiters = [RedisPubMedLimiter("redis://localhost", key, 10) for key in ("", " ", "a", " a ", "b")]
    try:
        assert limiters[0].bucket == limiters[1].bucket
        assert limiters[2].bucket == limiters[3].bucket
        assert len({limiter.bucket for limiter in limiters}) == 3
    finally:
        for limiter in limiters:
            asyncio.run(limiter.close())


def _request_slots(redis_url, api_key, rate, queue):
    async def run():
        async with PubMedClient(api_key=api_key, rate_limit=rate, redis_url=redis_url) as client:
            for _ in range(3):
                await client._throttle()
                queue.put(time.monotonic())
    asyncio.run(run())


@pytest.mark.parametrize("api_key,rate", [("", 3), ("integration-fixture-key", 10)])
def test_real_redis_enforces_one_budget_across_processes(api_key, rate):
    redis_url = os.environ.get("BIBMEDED_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("set BIBMEDED_TEST_REDIS_URL to run real Redis concurrency coverage")
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [context.Process(target=_request_slots, args=(redis_url, api_key, rate, queue)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        timestamps = sorted(queue.get(timeout=15) for _ in range(6))
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        assert timestamps[-1] - timestamps[0] >= 4.8 / rate
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
        queue.close()
        queue.join_thread()
