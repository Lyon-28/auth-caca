from fastapi import Request, HTTPException
from app.redis_client import redis

def rate_limiter(key_prefix: str, limit: int, window_seconds: int):
    async def dependency(request: Request):
        identity = request.client.host if request.client else "unknown"
        key = f"rl:{key_prefix}:{identity}"
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        if current > limit:
            ttl = await redis.ttl(key)
            raise HTTPException(status_code=429, detail={"code": "rate_limited", "message": "too many requests", "retry_after": ttl})
    return dependency

def rate_limiter_by_key(key_prefix: str, key: str, limit: int, window_seconds: int):
    async def dependency():
        rkey = f"rl:{key_prefix}:{key}"
        current = await redis.incr(rkey)
        if current == 1:
            await redis.expire(rkey, window_seconds)
        if current > limit:
            ttl = await redis.ttl(rkey)
            raise HTTPException(status_code=429, detail={"code": "rate_limited", "message": "too many requests", "retry_after": ttl})
    return dependency