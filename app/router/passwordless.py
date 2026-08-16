import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User, Tenant
from app.schemas import MagicLinkRequest, MagicLinkVerify, OtpLoginRequest, OtpLoginVerify
from app.deps import get_tenant_from_api_key
from app.mfa import generate_otp_code
from app.security import hash_token
from app.redis_client import redis
from app.response import ok, fail
from app.rate_limit import rate_limiter
from app.tasks import send_email_task, send_sms_task
from app.config import settings
from app.router.auth import issue_tokens

router = APIRouter(prefix="/auth", tags=["passwordless"])

@router.post("/magic-link/request", dependencies=[Depends(rate_limiter("magic_link", 5, 3600))])
async def magic_link_request(body: MagicLinkRequest, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(tenant_id=tenant.id, email=body.email, password_hash=None, email_verified=True)
        db.add(user)
        await db.commit()

    raw = uuid.uuid4().hex
    await redis.set(f"magic_link:{hash_token(raw)}", str(user.id), ex=settings.magic_link_ttl_seconds)
    link = f"{settings.frontend_url}/magic-login?token={raw}"
    subject = "Your login link"
    html = f'<p>Click to log in: <a href="{link}">{link}</a> (expires in {settings.magic_link_ttl_seconds // 60} minutes)</p>'
    send_email_task.delay(user.email, subject, html)
    return ok({"message": "magic link sent"})

@router.post("/magic-link/verify")
async def magic_link_verify(body: MagicLinkVerify, request: Request, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    key = f"magic_link:{hash_token(body.token)}"
    user_id = await redis.get(key)
    if not user_id:
        return fail("invalid_token", "magic link invalid or expired", status_code=400)
    await redis.delete(key)
    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("not_found", "user not found", status_code=404)
    access, refresh = await issue_tokens(db, user, request)
    return ok({"access_token": access, "refresh_token": refresh})

@router.post("/otp-login/request", dependencies=[Depends(rate_limiter("otp_login", 5, 3600))])
async def otp_login_request(body: OtpLoginRequest, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    code = generate_otp_code()
    await redis.set(f"otp_login:{tenant.id}:{body.phone}", code, ex=settings.otp_ttl_seconds)
    send_sms_task.delay(body.phone, f"Your Caca Auth login code is {code}")
    return ok({"message": "otp sent"})

@router.post("/otp-login/verify")
async def otp_login_verify(body: OtpLoginVerify, request: Request, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    key = f"otp_login:{tenant.id}:{body.phone}"
    stored = await redis.get(key)
    if not stored or stored != body.code:
        return fail("invalid_code", "invalid or expired otp", status_code=400)
    await redis.delete(key)

    result = await db.execute(select(User).where(User.phone == body.phone, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(tenant_id=tenant.id, email=f"{body.phone}@phone.caca-auth.local", phone=body.phone, phone_verified=True, password_hash=None)
        db.add(user)
        await db.commit()
    elif not user.phone_verified:
        user.phone_verified = True
        await db.commit()

    access, refresh = await issue_tokens(db, user, request)
    return ok({"access_token": access, "refresh_token": refresh})

@router.post("/anonymous")
async def anonymous_login(request: Request, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    user = User(tenant_id=tenant.id, email=f"anon_{uuid.uuid4().hex}@anonymous.caca-auth.local", password_hash=None, is_anonymous=True, email_verified=False)
    db.add(user)
    await db.flush()
    access, refresh = await issue_tokens(db, user, request)
    return ok({"access_token": access, "refresh_token": refresh, "user": {"id": str(user.id), "is_anonymous": True}}, status_code=201)