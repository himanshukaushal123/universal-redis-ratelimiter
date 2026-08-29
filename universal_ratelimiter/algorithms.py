from enum import Enum

class Algorithm(Enum):
    SLIDING_WINDOW_LOG = "SLIDING_WINDOW_LOG"
    FIXED_WINDOW = "FIXED_WINDOW"
    TOKEN_BUCKET = "TOKEN_BUCKET"

LUA_SLIDING_WINDOW_LOG = """
local key = KEYS[1]
local now_ts = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local request_id = ARGV[4]

local cutoff_ts = now_ts - window_ms
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff_ts)

local current_requests = redis.call('ZCARD', key)
local reset_ms = now_ts + window_ms

if current_requests >= max_requests then
    return {0, 0, reset_ms}
else
    redis.call('ZADD', key, now_ts, request_id)
    redis.call('PEXPIRE', key, window_ms)
    return {1, max_requests - current_requests - 1, reset_ms}
end
"""

LUA_FIXED_WINDOW = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_sec = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])

local current = redis.call('GET', key)
local reset_ms = now_ms + (window_sec * 1000)

if current and tonumber(current) >= limit then
    local ttl = redis.call('PTTL', key)
    if ttl > 0 then reset_ms = now_ms + ttl end
    return {0, 0, reset_ms}
end

current = redis.call('INCR', key)
if tonumber(current) == 1 then
    redis.call('EXPIRE', key, window_sec)
else
    local ttl = redis.call('PTTL', key)
    if ttl > 0 then reset_ms = now_ms + ttl end
end

local remaining = math.max(0, limit - tonumber(current))
return {1, remaining, reset_ms}
"""

LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_time_sec = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local requested = 1
local reset_ms = now_ms + (refill_time_sec * 1000)

local refill_rate = max_tokens / (refill_time_sec * 1000)

local hash_values = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(hash_values[1])
local last_refill = tonumber(hash_values[2])

if not tokens then
    tokens = max_tokens
    last_refill = now_ms
else
    local time_passed = math.max(0, now_ms - last_refill)
    local new_tokens = math.floor(time_passed * refill_rate)
    if new_tokens > 0 then
        tokens = math.min(max_tokens, tokens + new_tokens)
        last_refill = last_refill + (new_tokens / refill_rate)
    end
end

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('PEXPIRE', key, refill_time_sec * 1000)
    return {1, math.floor(tokens), reset_ms}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('PEXPIRE', key, refill_time_sec * 1000)
    return {0, math.floor(tokens), reset_ms}
end
"""

SCRIPTS = {
    Algorithm.SLIDING_WINDOW_LOG: LUA_SLIDING_WINDOW_LOG,
    Algorithm.FIXED_WINDOW: LUA_FIXED_WINDOW,
    Algorithm.TOKEN_BUCKET: LUA_TOKEN_BUCKET,
}
