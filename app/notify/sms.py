import httpx
from app.config import settings
from app.redis_client import redis
from app.notify.internal_alert import notify_internal_team

async def _zenziva(to: str, message: str):
    if not settings.zenziva_userkey or not settings.zenziva_passkey:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post("https://console.zenziva.net/reguler/api/sendsms/", data={
            "userkey": settings.zenziva_userkey, "passkey": settings.zenziva_passkey, "to": to, "message": message,
        })
        r.raise_for_status()

async def _twilio(to: str, message: str):
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10, auth=(settings.twilio_account_sid, settings.twilio_auth_token)) as client:
        r = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
            data={"From": settings.twilio_from, "To": to, "Body": message},
        )
        r.raise_for_status()

async def _vonage(to: str, message: str):
    if not settings.vonage_api_key or not settings.vonage_api_secret:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post("https://rest.nexmo.com/sms/json", data={
            "api_key": settings.vonage_api_key, "api_secret": settings.vonage_api_secret,
            "to": to, "from": "CacaAuth", "text": message,
        })
        r.raise_for_status()

async def _termii(to: str, message: str):
    if not settings.termii_api_key:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post("https://api.ng.termii.com/api/sms/send", json={
            "api_key": settings.termii_api_key, "to": to, "from": "CacaAuth", "sms": message, "type": "plain", "channel": "generic",
        })
        r.raise_for_status()

async def _fonnte(to: str, message: str):
    if not settings.fonnte_token:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10, headers={"Authorization": settings.fonnte_token}) as client:
        r = await client.post("https://api.fonnte.com/send", data={"target": to, "message": message})
        r.raise_for_status()

async def _wablas(to: str, message: str):
    if not settings.wablas_token:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"https://console.wablas.com/api/send-message?token={settings.wablas_token}", data={"phone": to, "message": message})
        r.raise_for_status()

async def _messagebird(to: str, message: str):
    if not settings.messagebird_api_key:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10, headers={"Authorization": f"AccessKey {settings.messagebird_api_key}"}) as client:
        r = await client.post("https://rest.messagebird.com/messages", data={"originator": "CacaAuth", "recipients": to, "body": message})
        r.raise_for_status()

async def _firebase(to: str, message: str):
    raise RuntimeError("skip")

async def _supabase(to: str, message: str):
    raise RuntimeError("skip")

async def _telegram(to: str, message: str):
    raise RuntimeError("skip")

async def _whatsapp_cloud(to: str, message: str):
    if not settings.whatsapp_cloud_token or not settings.whatsapp_cloud_phone_id:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10, headers={"Authorization": f"Bearer {settings.whatsapp_cloud_token}"}) as client:
        r = await client.post(
            f"https://graph.facebook.com/v20.0/{settings.whatsapp_cloud_phone_id}/messages",
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}},
        )
        r.raise_for_status()

async def _ntfy(to: str, message: str):
    if not settings.ntfy_topic_url:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(settings.ntfy_topic_url, content=f"SMS to {to}: {message}".encode())
        r.raise_for_status()

async def _gotify(to: str, message: str):
    if not settings.gotify_url or not settings.gotify_token:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{settings.gotify_url}/message?token={settings.gotify_token}", json={"title": "SMS fallback", "message": f"To {to}: {message}", "priority": 5})
        r.raise_for_status()

async def _apprise(to: str, message: str):
    if not settings.apprise_url:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(settings.apprise_url, json={"title": "SMS fallback", "body": f"To {to}: {message}"})
        r.raise_for_status()

async def _textbee(to: str, message: str):
    if not settings.textbee_api_key or not settings.textbee_device_id:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10, headers={"x-api-key": settings.textbee_api_key}) as client:
        r = await client.post(f"https://api.textbee.dev/api/v1/gateway/devices/{settings.textbee_device_id}/send-sms", json={"recipients": [to], "message": message})
        r.raise_for_status()

async def _ui_alert_fallback(to: str, message: str):
    await redis.rpush(f"ui_alerts:{to}", message)
    await redis.expire(f"ui_alerts:{to}", 60 * 60 * 24)

PROVIDER_CHAIN = [
    _zenziva, _twilio, _vonage, _termii, _fonnte, _wablas, _messagebird,
    _firebase, _supabase, _telegram, _whatsapp_cloud, _ntfy, _gotify, _apprise, _textbee,
]

async def send_sms(to: str, message: str):
    for provider in PROVIDER_CHAIN:
        try:
            await provider(to, message)
            return
        except Exception:
            continue
    await _ui_alert_fallback(to, message)
    await notify_internal_team(f"All SMS providers failed for {to}")