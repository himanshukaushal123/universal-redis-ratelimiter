import pytest
import asyncio
import redis
from universal_ratelimiter import AsyncRateLimiter, SyncRateLimiter, Algorithm

# FastAPI Setup
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.testclient import TestClient
from universal_ratelimiter.fastapi_plugin import RateLimitDependency

# Django Setup
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEFAULT_CHARSET='utf-8',
        ROOT_URLCONF='',
        DEBUG=True,
    )
import django
django.setup()
from django.http import HttpRequest, JsonResponse
from universal_ratelimiter.django_plugin import django_rate_limit, async_django_rate_limit

TEST_REDIS_URL = "redis://localhost:6379/1"

from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_fastapi_plugin_isolation():
    """
    Tests that the FastAPI dependency correctly parses custom API keys,
    returning standard headers, and properly isolates limits between users.
    """
    r = redis.Redis.from_url(TEST_REDIS_URL)
    r.flushdb()
    r.close()

    limiter = AsyncRateLimiter(TEST_REDIS_URL)
    app = FastAPI()
    
    def extract_api_key(request: Request):
        return request.headers.get("X-API-KEY", "anonymous")
    
    dep = RateLimitDependency(limiter, limit=2, window_sec=10, client_id_extractor=extract_api_key)
    
    @app.get("/test", dependencies=[Depends(dep)])
    def test_route():
        return {"status": "ok"}
        
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User A traffic
        r1 = await client.get("/test", headers={"X-API-KEY": "UserA"})
        r2 = await client.get("/test", headers={"X-API-KEY": "UserA"})
        r3 = await client.get("/test", headers={"X-API-KEY": "UserA"})
        
        assert r1.status_code == 200, "First request blocked!"
        assert r2.status_code == 200, "Second request blocked!"
        assert r3.status_code == 429, "Limit exceeded but request allowed!"
        
        assert "X-RateLimit-Remaining" in r1.headers
        assert r1.headers["X-RateLimit-Remaining"] == "1"
        assert r3.headers["X-RateLimit-Remaining"] == "0"
        
        # User B traffic (Should be entirely unimpacted by User A's 429)
        r_b = await client.get("/test", headers={"X-API-KEY": "UserB"})
        assert r_b.status_code == 200, "User B unfairly rate limited by User A's isolation block!"
        assert r_b.headers["X-RateLimit-Remaining"] == "1"

def test_django_plugin_isolation():
    """
    Tests that the Django synchronous decorator correctly parses custom
    user IDs, returning standard headers, and properly isolates limits.
    """
    r = redis.Redis.from_url(TEST_REDIS_URL)
    r.flushdb()
    r.close()

    limiter = SyncRateLimiter(TEST_REDIS_URL)
    
    def extract_user_id(request: HttpRequest):
        return getattr(request, "custom_user_id", "anonymous")
        
    @django_rate_limit(limiter, limit=2, window_sec=10, client_id_extractor=extract_user_id)
    def test_view(request):
        return JsonResponse({"status": "ok"})
        
    def make_mock_request(user_id: str):
        req = HttpRequest()
        req.custom_user_id = user_id
        req.META = {}
        return req
        
    req_a1 = make_mock_request("UserA")
    req_a2 = make_mock_request("UserA")
    req_a3 = make_mock_request("UserA")
    
    req_b1 = make_mock_request("UserB")
    
    r1 = test_view(req_a1)
    r2 = test_view(req_a2)
    r3 = test_view(req_a3)
    
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    
    assert r1["X-RateLimit-Remaining"] == "1"
    assert r3["X-RateLimit-Remaining"] == "0"
    
    r_b = test_view(req_b1)
    assert r_b.status_code == 200, "User B unfairly rate limited by User A's isolation block!"
    assert r_b["X-RateLimit-Remaining"] == "1"

@pytest.mark.asyncio
async def test_django_async_plugin_isolation():
    """
    Tests the async Django decorator for identical isolated behaviors.
    """
    r = redis.Redis.from_url(TEST_REDIS_URL)
    r.flushdb()
    r.close()

    limiter = AsyncRateLimiter(TEST_REDIS_URL)
    
    def extract_user_id(request: HttpRequest):
        return getattr(request, "custom_user_id", "anonymous")
        
    @async_django_rate_limit(limiter, limit=2, window_sec=10, client_id_extractor=extract_user_id)
    async def test_view(request):
        return JsonResponse({"status": "ok"})
        
    def make_mock_request(user_id: str):
        req = HttpRequest()
        req.custom_user_id = user_id
        req.META = {}
        return req
        
    r1 = await test_view(make_mock_request("UserA"))
    r2 = await test_view(make_mock_request("UserA"))
    r3 = await test_view(make_mock_request("UserA"))
    
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    
    r_b = await test_view(make_mock_request("UserB"))
    assert r_b.status_code == 200, "User B unfairly block!"
