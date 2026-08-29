import pytest
import asyncio
from universal_ratelimiter import AsyncRateLimiter, Algorithm

TEST_REDIS_URL = "redis://localhost:6379/1"

@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", [
    Algorithm.SLIDING_WINDOW_LOG,
    Algorithm.FIXED_WINDOW,
    Algorithm.TOKEN_BUCKET
])
async def test_algorithmic_concurrency_and_uuid_collisions(algorithm):
    """
    Simulates a heavy concurrent load where multiple requests are fired
    on the exact same millisecond. This explicitly validates that UUIDs 
    prevent ZSET overwrites in Sliding Window, and that atomic execution
    stops race conditions across all algorithms.
    """
    # Initialize and clear the test DB
    limiter = AsyncRateLimiter(TEST_REDIS_URL)
    r = await limiter.get_redis_pool()
    await r.flushdb()
    
    client_id = f"test_client_{algorithm.name}"
    limit = 5
    window_sec = 2

    # Fire 20 exact-concurrent requests using evaluate instead of is_allowed
    tasks = [limiter.evaluate(client_id, limit, window_sec, algorithm) for _ in range(20)]
    results = await asyncio.gather(*tasks)

    # Calculate results
    allowed_count = sum([1 for r in results if r.allowed])
    rejected_count = len(results) - allowed_count
    
    assert allowed_count == limit, f"{algorithm.name} failed! Erroneously allowed {allowed_count} requests instead of {limit}."
    assert rejected_count == len(tasks) - limit

    # Check headers on an allowed request
    valid_result = next(r for r in results if r.allowed)
    assert valid_result.remaining >= 0
    assert valid_result.reset_epoch_ms > 0
    
    await limiter.close()
