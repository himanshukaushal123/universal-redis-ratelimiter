try:
    from fastapi import Request, HTTPException
except ImportError:
    raise ImportError("FastAPI is required for the universal_ratelimiter.fastapi_plugin. Install using pip install universal-redis-ratelimiter[fastapi]")

from typing import Callable, Awaitable, Optional
from .core import AsyncRateLimiter
from .algorithms import Algorithm

def get_client_ip(request: Request) -> str:
    """Default client ID extractor using the request host IP."""
    if request.client:
        return request.client.host
    return "unknown"

def RateLimitDependency(
    limiter: AsyncRateLimiter, 
    limit: int = 5, 
    window_sec: int = 10,
    algorithm: Algorithm = Algorithm.SLIDING_WINDOW_LOG,
    client_id_extractor: Optional[Callable[[Request], str]] = None
) -> Callable[[Request], Awaitable[None]]:
    """
    Returns a FastAPI dependency that checks the rate limit.
    Raises HTTPException(429) if limit is exceeded.
    """
    extractor = client_id_extractor or get_client_ip

    async def dependency(request: Request):
        client_id = extractor(request)
        allowed = await limiter.is_allowed(client_id, limit, window_sec, algorithm)
        if not allowed:
            raise HTTPException(status_code=429, detail="Too Many Requests")

    return dependency
