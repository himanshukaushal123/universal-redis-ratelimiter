from enum import Enum

class Algorithm(Enum):
    SLIDING_WINDOW_LOG = "SLIDING_WINDOW_LOG"
    FIXED_WINDOW = "FIXED_WINDOW"
    TOKEN_BUCKET = "TOKEN_BUCKET"

# ==========================================
# SLIDING WINDOW LOG
# ==========================================
# Very accurate. Keeps every timestamp.
# KEYS[1]: limit key
# ARGV[1]: current timestamp ms
# ARGV[2]: window size ms
# ARGV[3]: limit
# ARGV[4]: unique request id
LUA_SLIDING_WINDOW_LOG = """
local key = KEYS[1]
local now_ts = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local request_id = ARGV[4]

local cutoff_ts = now_ts - window_ms
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff_ts)

local current_requests = redis.call('ZCARD', key)
if current_requests >= max_requests then
    return 0
else
    redis.call('ZADD', key, now_ts, request_id)
    redis.call('PEXPIRE', key, window_ms)
    return 1
end
"""

# ==========================================
# FIXED WINDOW
# ==========================================
# Fast, low memory. Susceptible to boundary spikes.
# KEYS[1]: limit key
# ARGV[1]: limit
# ARGV[2]: window size seconds
LUA_FIXED_WINDOW = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_sec = tonumber(ARGV[2])

local current = redis.call('GET', key)
if current and tonumber(current) >= limit then
    return 0
end

current = redis.call('INCR', key)
if tonumber(current) == 1 then
    redis.call('EXPIRE', key, window_sec)
end
return 1
"""

# ==========================================
# TOKEN BUCKET
# ==========================================
# Good for handling burst traffic smoothly. 
# KEYS[1]: limit key
# ARGV[1]: max tokens (limit)
# ARGV[2]: refill time in seconds (window_sec)
# ARGV[3]: current timestamp ms
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_time_sec = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local requested = 1

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
    return 1
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('PEXPIRE', key, refill_time_sec * 1000)
    return 0
end
"""

SCRIPTS = {
    Algorithm.SLIDING_WINDOW_LOG: LUA_SLIDING_WINDOW_LOG,
    Algorithm.FIXED_WINDOW: LUA_FIXED_WINDOW,
    Algorithm.TOKEN_BUCKET: LUA_TOKEN_BUCKET,
}
