try:
    from fastapi import Request, Response, HTTPException
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
) -> Callable[[Request, Response], Awaitable[None]]:
    """
    Returns a FastAPI dependency that checks the rate limit.
    Injects Standard X-RateLimit headers.
    Raises HTTPException(429) if limit is exceeded.
    """
    extractor = client_id_extractor or get_client_ip

    async def dependency(request: Request, response: Response):
        client_id = extractor(request)
        result = await limiter.evaluate(client_id, limit, window_sec, algorithm)
        
        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(result.reset_epoch_ms // 1000)
        }
        
        # Merge headers to the successful response
        for k, v in headers.items():
            response.headers[k] = v

        if not result.allowed:
            raise HTTPException(status_code=429, detail="Too Many Requests", headers=headers)

    return dependency
