"""One request budget per NCBI key across all workers using the same Redis."""
import asyncio
import hashlib
import math


_ACQUIRE = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local next_request = tonumber(redis.call('GET', KEYS[1]) or '0')
if next_request > now then
    return next_request - now
end
local interval = tonumber(ARGV[1])
redis.call('SET', KEYS[1], now + interval, 'PX', interval + 1000)
return 0
"""


class RedisPubMedLimiter:
    def __init__(self, redis_url: str, api_key: str, rate_limit: float):
        from redis.asyncio import Redis
        bucket = hashlib.sha256(api_key.strip().encode()).hexdigest() if api_key.strip() else "no-key"
        self.bucket = f"bibmeded:pubmed:rate:{bucket}"
        self.interval_ms = math.ceil(1000 / rate_limit)
        self._redis = Redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)

    async def acquire(self) -> None:
        while True:
            wait_ms = await self._redis.eval(_ACQUIRE, 1, self.bucket, self.interval_ms)
            if wait_ms == 0:
                return
            await asyncio.sleep(wait_ms / 1000)

    async def close(self) -> None:
        await self._redis.aclose()
