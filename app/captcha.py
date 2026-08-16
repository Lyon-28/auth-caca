import httpx
from app.config import settings

async def verify_captcha(token: str | None) -> bool:
    if not settings.turnstile_secret_key:
        return True
    if not token:
        return False
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": settings.turnstile_secret_key, "response": token},
        )
        data = r.json()
        return bool(data.get("success"))