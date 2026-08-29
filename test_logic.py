import asyncio
from universal_ratelimiter.core import AsyncRateLimiter

async def test_concurrent_rate_limiting():
    print("--- Testing Rate Limiter Logic (Concurrency) ---")
    
    # 1. Initialize the Rate Limiter
    limiter = AsyncRateLimiter("redis://localhost:6379/0")
    client_ip = "127.0.0.1"
    
    # We want a maximum of 5 requests per 10 seconds
    limit = 5
    window_sec = 10
    
    print(f"Firing 12 concurrent requests for {client_ip}...")
    
    # 2. Fire 12 exact-simultaneous requests! 
    # Because we use asyncio.gather, these happen concurrently.
    tasks = [limiter.is_allowed(client_ip, limit, window_sec) for _ in range(12)]
    
    results = await asyncio.gather(*tasks)
    
    # 3. Analyze the results
    allowed_count = sum(results)
    rejected_count = len(results) - allowed_count
    
    print(f"Total Requests Fired: {len(results)}")
    print(f"Allowed (returns True):  {allowed_count}  (Expected: {limit})")
    print(f"Rejected (returns False): {rejected_count}  (Expected: {len(results) - limit})")
    
    print("-" * 40)
    if allowed_count == limit:
        print("SUCCESS! \nThe Lua Script and UUID generation successfully prevented distributed race conditions.")
    else:
        print("FAILED! \nRace condition detected.")
        
    await limiter.close()

if __name__ == "__main__":
    asyncio.run(test_concurrent_rate_limiting())
