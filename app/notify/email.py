import httpx
import aiosmtplib
from email.message import EmailMessage
from app.config import settings
from app.redis_client import redis
from app.notify.internal_alert import notify_internal_team

async def _resend(to: str, subject: str, html: str):
    if not settings.resend_api_key:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.mail_from, "to": [to], "subject": subject, "html": html},
        )
        r.raise_for_status()

async def _brevo(to: str, subject: str, html: str):
    if not settings.brevo_api_key:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.brevo_api_key},
            json={"sender": {"email": settings.mail_from}, "to": [{"email": to}], "subject": subject, "htmlContent": html},
        )
        r.raise_for_status()

async def _mailjet(to: str, subject: str, html: str):
    if not settings.mailjet_api_key or not settings.mailjet_secret_key:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10, auth=(settings.mailjet_api_key, settings.mailjet_secret_key)) as client:
        r = await client.post(
            "https://api.mailjet.com/v3.1/send",
            json={"Messages": [{"From": {"Email": settings.mail_from}, "To": [{"Email": to}], "Subject": subject, "HTMLPart": html}]},
        )
        r.raise_for_status()

async def _smtp_gmail(to: str, subject: str, html: str):
    if not settings.smtp_gmail_user or not settings.smtp_gmail_password:
        raise RuntimeError("skip")
    msg = EmailMessage()
    msg["From"] = settings.smtp_gmail_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.add_alternative(html, subtype="html")
    await aiosmtplib.send(
        msg, hostname="smtp.gmail.com", port=587, start_tls=True,
        username=settings.smtp_gmail_user, password=settings.smtp_gmail_password,
    )

async def _mailgun(to: str, subject: str, html: str):
    if not settings.mailgun_api_key or not settings.mailgun_domain:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10, auth=("api", settings.mailgun_api_key)) as client:
        r = await client.post(
            f"https://api.mailgun.net/v3/{settings.mailgun_domain}/messages",
            data={"from": settings.mail_from, "to": to, "subject": subject, "html": html},
        )
        r.raise_for_status()

async def _sendgrid(to: str, subject: str, html: str):
    if not settings.sendgrid_api_key:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": settings.mail_from},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
            },
        )
        r.raise_for_status()

async def _firebase(to: str, subject: str, html: str):
    raise RuntimeError("skip")

async def _supabase(to: str, subject: str, html: str):
    raise RuntimeError("skip")

async def _ntfy(to: str, subject: str, html: str):
    if not settings.ntfy_topic_url:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(settings.ntfy_topic_url, content=f"{subject} -> {to}".encode())
        r.raise_for_status()

async def _gotify(to: str, subject: str, html: str):
    if not settings.gotify_url or not settings.gotify_token:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{settings.gotify_url}/message?token={settings.gotify_token}",
            json={"title": subject, "message": f"Email to {to} (provider fallback)", "priority": 5},
        )
        r.raise_for_status()

async def _apprise(to: str, subject: str, html: str):
    if not settings.apprise_url:
        raise RuntimeError("skip")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(settings.apprise_url, json={"title": subject, "body": f"To: {to}"})
        r.raise_for_status()

async def _ui_alert_fallback(to: str, subject: str, html: str):
    await redis.rpush(f"ui_alerts:{to}", subject)
    await redis.expire(f"ui_alerts:{to}", 60 * 60 * 24)

PROVIDER_CHAIN = [_resend, _brevo, _mailjet, _smtp_gmail, _mailgun, _sendgrid, _firebase, _supabase, _ntfy, _gotify, _apprise]

async def send_email(to: str, subject: str, html: str):
    for provider in PROVIDER_CHAIN:
        try:
            await provider(to, subject, html)
            return
        except Exception:
            continue
    await _ui_alert_fallback(to, subject, html)
    await notify_internal_team(f"All email providers failed for {to} — subject: {subject}")