import time
import uuid
import logging
import redis
import redis.asyncio as redis_async
from typing import Any, Tuple

from .algorithms import Algorithm, SCRIPTS

logger = logging.getLogger("universal_ratelimiter")

def _prepare_lua_args(algorithm: Algorithm, client_id: str, limit: int, window_sec: int) -> Tuple[list, list]:
    now_ms = int(time.time() * 1000)
    key = f"{algorithm.value}:{client_id}"
    
    if algorithm == Algorithm.SLIDING_WINDOW_LOG:
        req_id = f"{now_ms}-{uuid.uuid4().hex}"
        window_ms = window_sec * 1000
        return [key], [now_ms, window_ms, limit, req_id]
        
    elif algorithm == Algorithm.FIXED_WINDOW:
        return [key], [limit, window_sec]
        
    elif algorithm == Algorithm.TOKEN_BUCKET:
        return [key], [limit, window_sec, now_ms]
        
    raise ValueError(f"Unsupported algorithm: {algorithm}")


class AsyncRateLimiter:
    """
    Async Redis-backed rate limiter instance. (For FastAPI or modern async Frameworks)
    """
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_client = None
        self._scripts = {}

    async def get_redis_pool(self) -> redis_async.Redis:
        if self.redis_client is None:
            self.redis_client = redis_async.from_url(
                self.redis_url, 
                encoding="utf-8", 
                decode_responses=True
            )
        return self.redis_client

    async def load_script(self, algorithm: Algorithm) -> Any:
        r = await self.get_redis_pool()
        if algorithm not in self._scripts:
            self._scripts[algorithm] = r.register_script(SCRIPTS[algorithm])
        return self._scripts[algorithm]

    async def close(self):
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            
    async def is_allowed(self, client_id: str, limit: int, window_sec: int, algorithm: Algorithm = Algorithm.SLIDING_WINDOW_LOG) -> bool:
        script = await self.load_script(algorithm)
        keys, args = _prepare_lua_args(algorithm, client_id, limit, window_sec)
        
        allowed = await script(keys=keys, args=args)
        return int(allowed) == 1


class SyncRateLimiter:
    """
    Synchronous Redis-backed rate limiter instance. (For Django)
    """
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_client = None
        self._scripts = {}

    def get_redis_pool(self) -> redis.Redis:
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                self.redis_url, 
                encoding="utf-8", 
                decode_responses=True
            )
        return self.redis_client

    def load_script(self, algorithm: Algorithm) -> Any:
        r = self.get_redis_pool()
        if algorithm not in self._scripts:
            self._scripts[algorithm] = r.register_script(SCRIPTS[algorithm])
        return self._scripts[algorithm]

    def is_allowed(self, client_id: str, limit: int, window_sec: int, algorithm: Algorithm = Algorithm.SLIDING_WINDOW_LOG) -> bool:
        script = self.load_script(algorithm)
        keys, args = _prepare_lua_args(algorithm, client_id, limit, window_sec)
        
        allowed = script(keys=keys, args=args)
        return int(allowed) == 1
