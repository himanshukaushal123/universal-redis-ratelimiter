from functools import wraps
import asyncio
try:
    from django.http import JsonResponse
except ImportError:
    raise ImportError("Django is required for the universal_ratelimiter.django_plugin. Install using pip install universal-redis-ratelimiter[django]")

from .core import SyncRateLimiter, AsyncRateLimiter
from .algorithms import Algorithm

def django_rate_limit(limiter: SyncRateLimiter, limit: int = 5, window_sec: int = 10, algorithm: Algorithm = Algorithm.SLIDING_WINDOW_LOG):
    """
    Django decorator to rate-limit a view synchronously.
    Returns 429 JSON response if limit is exceeded.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Extract Client IP from Django's HttpRequest
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                client_id = x_forwarded_for.split(',')[0]
            else:
                client_id = request.META.get('REMOTE_ADDR', "unknown")

            result = limiter.evaluate(client_id, limit, window_sec, algorithm)
            
            headers = {
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(result.reset_epoch_ms // 1000)
            }
            
            if not result.allowed:
                resp = JsonResponse({"error": "Too Many Requests"}, status=429)
            else:
                resp = view_func(request, *args, **kwargs)
                
            for k, v in headers.items():
                resp[k] = v
            return resp
        return _wrapped_view
    return decorator

def async_django_rate_limit(limiter: AsyncRateLimiter, limit: int = 5, window_sec: int = 10, algorithm: Algorithm = Algorithm.SLIDING_WINDOW_LOG):
    """
    Asynchronous Django decorator to rate-limit an `async def` view.
    Returns 429 JSON response if limit is exceeded.
    """
    def decorator(view_func):
        @wraps(view_func)
        async def _wrapped_view(request, *args, **kwargs):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                client_id = x_forwarded_for.split(',')[0]
            else:
                client_id = request.META.get('REMOTE_ADDR', "unknown")

            result = await limiter.evaluate(client_id, limit, window_sec, algorithm)
            
            headers = {
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(result.reset_epoch_ms // 1000)
            }
            
            if not result.allowed:
                resp = JsonResponse({"error": "Too Many Requests"}, status=429)
            else:
                resp = await view_func(request, *args, **kwargs)
                
            for k, v in headers.items():
                resp[k] = v
            return resp
        return _wrapped_view
    return decorator
