import json
from app.redis_client import redis

PROFILE_TTL = 300

async def get_cached_profile(user_id: str) -> dict | None:
    raw = await redis.get(f"profile:{user_id}")
    return json.loads(raw) if raw else None

async def set_cached_profile(user_id: str, data: dict):
    await redis.set(f"profile:{user_id}", json.dumps(data), ex=PROFILE_TTL)

async def invalidate_profile_cache(user_id: str):
    await redis.delete(f"profile:{user_id}")