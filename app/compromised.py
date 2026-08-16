import hashlib
import httpx
from app.config import settings

async def is_password_pwned(password: str) -> bool:
    if not settings.hibp_enabled:
        return False
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
            r.raise_for_status()
    except Exception:
        return False
    for line in r.text.splitlines():
        parts = line.split(":")
        if len(parts) == 2 and parts[0] == suffix:
            return True
    return False