import httpx
from app.config import settings

async def notify_internal_team(message: str):
    async with httpx.AsyncClient(timeout=5) as client:
        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": settings.telegram_chat_id, "text": f"[Caca Auth] {message}"},
                )
                return
            except Exception:
                pass
        if settings.ntfy_topic_url:
            try:
                await client.post(settings.ntfy_topic_url, content=message.encode())
                return
            except Exception:
                pass
        if settings.gotify_url and settings.gotify_token:
            try:
                await client.post(
                    f"{settings.gotify_url}/message?token={settings.gotify_token}",
                    json={"title": "Caca Auth Alert", "message": message, "priority": 8},
                )
                return
            except Exception:
                pass
        if settings.apprise_url:
            try:
                await client.post(settings.apprise_url, json={"body": message})
            except Exception:
                pass