import pytest
import redis.exceptions
from universal_ratelimiter import AsyncRateLimiter, Algorithm

@pytest.mark.asyncio
async def test_redis_down_fail_closed():
    """
    Validates that when fail_open=False (default behavior), an unreachable 
    Redis server forces the limiter to silently reject all requests (fail closed).
    """
    broken_url = "redis://localhost:9999/0"
    limiter = AsyncRateLimiter(broken_url, fail_open=False)
    
    # Should safely catch the RedisError and return False (blocked)
    allowed = await limiter.is_allowed("ghost_client", 5, 10, Algorithm.SLIDING_WINDOW_LOG)
    assert allowed is False, "Fail-closed mode did not block the request upon disconnect!"
    
    try: await limiter.close()
    except Exception: pass

@pytest.mark.asyncio
async def test_redis_down_fail_open():
    """
    Validates that when fail_open=True, an unreachable Redis server 
    forces the limiter to allow all requests through (prioritizing availability).
    """
    broken_url = "redis://localhost:9999/0"
    limiter = AsyncRateLimiter(broken_url, fail_open=True)
    
    # Should safely catch the RedisError and return True (allowed)
    allowed = await limiter.is_allowed("ghost_client_2", 5, 10, Algorithm.SLIDING_WINDOW_LOG)
    assert allowed is True, "Fail-open mode did not allow the request upon disconnect!"
    
    try: await limiter.close()
    except Exception: pass
