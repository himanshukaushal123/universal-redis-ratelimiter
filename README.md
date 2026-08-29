# Universal Redis Rate Limiter

A distributed, framework-agnostic rate limiter backed by Redis. Designed to prevent race conditions during horizontally scaled, distributed use and provides out-of-the-box support for both **FastAPI** (async) and **Django** (sync,async).

## Features
- 🚀 **Framework Agnostic**: Native plugins for both Django and FastAPI.
- 🔒 **Distributed Safety**: Uses atomic Redis Lua scripts + UUIDs to completely eliminate race conditions.
- ⚙️ **Multi-Algorithmic**: Native support for configurable algorithms including `SLIDING_WINDOW_LOG`, `FIXED_WINDOW`, and `TOKEN_BUCKET`.

## Installation

You can install this package directly from GitHub. Choose the installation command based on your web framework.

**For FastAPI:**
```bash
pip install "universal-redis-ratelimiter[fastapi] @ git+https://github.com/himanshukaushal123/universal-redis-ratelimiter.git"
```

**For Django:**
```bash
pip install "universal-redis-ratelimiter[django] @ git+https://github.com/himanshukaushal123/universal-redis-ratelimiter.git"
```

---

## Quickstart: FastAPI

Applying the rate limiter as a Dependency in FastAPI. You can select your algorithm using the `Algorithm` Enum.

```python
from fastapi import FastAPI, Depends
from universal_ratelimiter import AsyncRateLimiter, Algorithm
from universal_ratelimiter.fastapi_plugin import RateLimitDependency

app = FastAPI()

# Connect to Redis
limiter = AsyncRateLimiter("redis://localhost:6379/0")

# Limit to 5 requests per 10 seconds using the Token Bucket algorithm
rate_limit_dep = RateLimitDependency(
    limiter, 
    limit=5, 
    window_sec=10, 
    algorithm=Algorithm.TOKEN_BUCKET
)

@app.get("/api/burst-data", dependencies=[Depends(rate_limit_dep)])
async def get_data():
    return {"message": "Success! You are within your rate limit."}
```

## Handling Redis Failures (Fail-Open vs Fail-Closed)

In distributed systems, what happens if your rate-limiting dependency (Redis) goes offline? This package allows you to explicitly configure your fallback behavior using the `fail_open` parameter:

```python
# Fail-Closed (Default): 
# If Redis goes down, all requests are safely blocked to protect your databases.
limiter = AsyncRateLimiter("redis://localhost:6379/0", fail_open=False)

# Fail-Open (Availability explicitly prioritized): 
# If Redis goes down, requests are silently allowed through without rate limiting.
limiter = AsyncRateLimiter("redis://localhost:6379/0", fail_open=True)
```

---

## Quickstart: Django

Applying the rate limiter as a View Decorator in Django. 

```python
from django.http import JsonResponse
from universal_ratelimiter import SyncRateLimiter, AsyncRateLimiter, Algorithm
from universal_ratelimiter.django_plugin import django_rate_limit, async_django_rate_limit

# Connect to Redis natively
limiter = SyncRateLimiter("redis://localhost:6379/0")

# Limit to 5 requests per 10 seconds using Fixed Window
@django_rate_limit(limiter, limit=5, window_sec=10, algorithm=Algorithm.FIXED_WINDOW)
def my_protected_view(request):
    return JsonResponse({"message": "Success! You are within your rate limit."})
```

### Asynchronous Django Views:
If you are using modern `async def` views in Django, utilize our async decorator to prevent blocking the ASGI event loop:

```python
from django.http import JsonResponse
from universal_ratelimiter import AsyncRateLimiter, Algorithm
from universal_ratelimiter.django_plugin import async_django_rate_limit

# Use the AsyncRateLimiter!
async_limiter = AsyncRateLimiter("redis://localhost:6379/0")

# Pass the chosen Algorithm to the async decorator
@async_django_rate_limit(async_limiter, limit=5, window_sec=10, algorithm=Algorithm.TOKEN_BUCKET)
async def my_async_protected_view(request):
    return JsonResponse({"message": "Success! Async Django rate limit passed."})
```

## How It Works
The engine uses **Atomic Lua Scripts** dynamically routed via an Enum configuration. When multiple concurrent requests occur on horizontally scaled servers at the exact same millisecond, the Lua scripts utilize UUID generation combined with atomic executions to mathematically guarantee that your exact algorithmic limit will never be exceeded via race condition bypassing.
