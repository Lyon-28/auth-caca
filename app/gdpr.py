import json
import csv
import io
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, UserPreference, Session, AuditLog, OAuthAccount, MfaFactor

async def collect_user_data(db: AsyncSession, user: User) -> dict:
    prefs = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    pref = prefs.scalar_one_or_none()
    sessions = await db.execute(select(Session).where(Session.user_id == user.id))
    logs = await db.execute(select(AuditLog).where(AuditLog.user_id == user.id))
    oauth = await db.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
    factors = await db.execute(select(MfaFactor).where(MfaFactor.user_id == user.id))

    return {
        "profile": {
            "id": str(user.id), "email": user.email, "phone": user.phone, "name": user.name,
            "bio": user.bio, "email_verified": user.email_verified, "created_at": user.created_at.isoformat(),
        },
        "preferences": {
            "language": pref.language, "timezone": pref.timezone,
            "notify_email": pref.notify_email, "notify_sms": pref.notify_sms,
        } if pref else {},
        "sessions": [{"ip": s.ip_address, "user_agent": s.user_agent, "created_at": s.created_at.isoformat()} for s in sessions.scalars().all()],
        "audit_logs": [{"action": l.action, "ip": l.ip_address, "created_at": l.created_at.isoformat()} for l in logs.scalars().all()],
        "oauth_accounts": [{"provider": o.provider, "email": o.email} for o in oauth.scalars().all()],
        "mfa_factors": [{"type": f.type, "confirmed": f.confirmed} for f in factors.scalars().all()],
    }

def to_json_bytes(data: dict) -> bytes:
    return json.dumps(data, indent=2).encode()

def to_csv_bytes(data: dict) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    for section, content in data.items():
        if isinstance(content, dict):
            for k, v in content.items():
                writer.writerow([section, k, v])
        elif isinstance(content, list):
            for i, item in enumerate(content):
                for k, v in item.items():
                    writer.writerow([f"{section}[{i}]", k, v])
    return buf.getvalue().encode()