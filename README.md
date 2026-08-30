# Universal Redis Rate Limiter

[![CI](https://github.com/himanshukaushal123/universal-redis-ratelimiter/actions/workflows/ci.yml/badge.svg)](https://github.com/himanshukaushal123/universal-redis-ratelimiter/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/Tests-8%20passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.7%2B-blue.svg)

A distributed, framework-agnostic rate limiter backed by Redis. Designed to prevent race conditions during horizontally scaled, distributed use and provides out-of-the-box support for both **FastAPI** (async) and **Django** (sync,async).

## Features
- 🚀 **Framework Agnostic**: Native plugins for both Django and FastAPI.
- 🔒 **Distributed Safety**: Uses atomic Redis Lua scripts + UUIDs to completely eliminate race conditions.
- ⚙️ **Multi-Algorithmic**: Native support for configurable algorithms including `SLIDING_WINDOW_LOG`, `FIXED_WINDOW`, and `TOKEN_BUCKET`.
- 🛡️ **Industry Standard Headers**: Automatically injects exact `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` payloads to all responses.

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

---

## Pluggable Key Strategies (API Key, User ID, JWT, etc.)

By default, the rate limiter uses the incoming IP address as the unique limit identifier. In production workloads, you often need to limit by **User ID**, **JWT token**, or a specified **API Key**. 

Both our Django and FastAPI plugins securely support completely pluggable key extraction via the `client_id_extractor` parameter.

### FastAPI Example: Rate-Limit per API Key
```python
from fastapi import Request

def extract_api_key(request: Request) -> str:
    # Read a custom header overriding the default IP check
    return request.headers.get("X-API-KEY", "anonymous")

rate_limit_dep = RateLimitDependency(
    limiter, 
    limit=5, 
    window_sec=10, 
    client_id_extractor=extract_api_key
)
```

### Django Example: Rate-Limit per User ID
```python
def extract_user_id(request) -> str:
    # If the user is authenticated, isolate their limit per user_id; 
    # Otherwise, fallback safely to their IP address
    if request.user.is_authenticated:
        return f"user:{request.user.id}"
    return request.META.get('REMOTE_ADDR', "unknown")

@django_rate_limit(
    limiter, 
    limit=5, 
    window_sec=10, 
    client_id_extractor=extract_user_id
)
def my_protected_view(request):
    pass
```

## How It Works
The engine uses **Atomic Lua Scripts** dynamically routed via an Enum configuration. When multiple concurrent requests occur on horizontally scaled servers at the exact same millisecond, the Lua scripts utilize UUID generation combined with atomic executions to mathematically guarantee that your exact algorithmic limit will never be exceeded via race condition bypassing.

---

## Known Limitations: Redis Cluster

Currently, this library is out-of-the-box optimized for **Single-Node** and **Redis Sentinel** architectures via standard connection pools.

While our underlying Lua scripts are rigorously well-behaved (they only ever operate on a single `KEYS[1]` parameter to explicitly avoid the infamous Redis Cluster `CROSSSLOT Keys in request don't hash to the same slot` exceptions), the underlying engine currently automatically instantiates standard `redis.Redis` and `redis.asyncio.Redis` network clients. 

If your ecosystem runs a strictly distributed **Redis Cluster**, the rate limiter logic itself is completely hash-slot safe, but you will need to override the connection pool logic within `core.py` to instantiate `redis.cluster.RedisCluster` clients natively instead of the standard client to allow correct underlying slot routing.
