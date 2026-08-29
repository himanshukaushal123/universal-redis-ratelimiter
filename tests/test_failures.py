import pytest
import redis.exceptions
from universal_ratelimiter import AsyncRateLimiter, Algorithm

@pytest.mark.asyncio
async def test_redis_unreachable_exception():
    """
    Validates that the rate limiter gracefully surfaces ConnectionErrors
    when Redis is offline, allowing the backend framework to handle and log it.
    """
    broken_url = "redis://localhost:9999/0"
    limiter = AsyncRateLimiter(broken_url)
    
    with pytest.raises(redis.exceptions.ConnectionError):
        await limiter.is_allowed(
            client_id="ghost_client",
            limit=5, 
            window_sec=10, 
            algorithm=Algorithm.SLIDING_WINDOW_LOG
        )
    
    try:
        await limiter.close()
    except Exception:
        pass
