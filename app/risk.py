import httpx
from app.config import settings
from app.redis_client import redis

async def get_geo(ip: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.geoip_provider_url}/{ip}/json/")
            r.raise_for_status()
            data = r.json()
            return {"country": data.get("country_name"), "city": data.get("city")}
    except Exception:
        return {"country": None, "city": None}

async def assess_risk(user_id: str, ip: str, ua: str) -> dict:
    known_key = f"known_context:{user_id}"
    known = await redis.smembers(known_key)
    context = f"{ip}|{ua}"
    is_known = context in known
    await redis.sadd(known_key, context)
    await redis.expire(known_key, 60 * 60 * 24 * 90)

    geo = await get_geo(ip)
    return {"is_new_context": not is_known, "geo": geo, "requires_step_up": not is_known}