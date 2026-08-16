import uuid
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.models import User, Tenant, Session
from app.schemas import RegisterRequest, LoginRequest, RefreshRequest, LogoutRequest
from app.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, create_mfa_session
from app.response import ok, fail
from app.deps import get_tenant_from_api_key
from app.redis_client import redis
from app.notify.templates import verify_email_tpl, welcome_tpl, new_device_login_tpl
from app.tasks import send_email_task
from app.router.verify import _issue_token
from app.config import settings
from app.rate_limit import rate_limiter
from app.ip_control import check_ip_blacklist, register_ip_failure
from app.captcha import verify_captcha
from app.compromised import is_password_pwned
from app.risk import assess_risk
from app.sse import publish_event

router = APIRouter(prefix="/auth", tags=["auth"])

async def issue_tokens(db, user: User, request: Request, family_id: str | None = None):
    jti = uuid.uuid4().hex
    family_id = family_id or uuid.uuid4().hex
    access = create_access_token(str(user.id), str(user.tenant_id))
    refresh = create_refresh_token(str(user.id), str(user.tenant_id), jti, family_id)

    session = Session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        refresh_token_id=jti,
        family_id=family_id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.add(session)
    await db.commit()
    return access, refresh

@router.post("/register", dependencies=[Depends(check_ip_blacklist), Depends(rate_limiter("register", 10, 3600))])
async def register(body: RegisterRequest, request: Request, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(body.captcha_token):
        return fail("captcha_failed", "captcha verification failed", status_code=400)

    existing = await db.execute(select(User).where(User.email == body.email, User.tenant_id == tenant.id))
    if existing.scalar_one_or_none():
        return fail("user_exists", "email already registered", status_code=409)

    if await is_password_pwned(body.password):
        return fail("password_compromised", "this password has appeared in a data breach, choose another", status_code=400)

    user = User(tenant_id=tenant.id, email=body.email, password_hash=hash_password(body.password), email_verified=False)
    db.add(user)
    await db.flush()

    access, refresh = await issue_tokens(db, user, request)

    raw = await _issue_token(db, user, "verify_email", 60 * 24)
    link = f"{settings.frontend_url}/verify-email?token={raw}"
    subject, html = verify_email_tpl(link)
    send_email_task.delay(user.email, subject, html)
    w_subject, w_html = welcome_tpl(user.email)
    send_email_task.delay(user.email, w_subject, w_html)

    return ok({"access_token": access, "refresh_token": refresh, "user": {"id": str(user.id), "email": user.email, "email_verified": user.email_verified}}, status_code=201)

@router.post("/login", dependencies=[Depends(check_ip_blacklist), Depends(rate_limiter("login", 20, 300))])
async def login(body: LoginRequest, request: Request, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(body.captcha_token):
        return fail("captcha_failed", "captcha verification failed", status_code=400)

    ip = request.client.host if request.client else "unknown"
    result = await db.execute(select(User).where(User.email == body.email, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()

    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        return fail("account_locked", "account temporarily locked due to too many failed attempts", status_code=423)

    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_fail_threshold:
                user.locked_until = datetime.now(timezone.utc) + timedelta(seconds=settings.lockout_duration_seconds)
                user.failed_login_count = 0
            await db.commit()
        await register_ip_failure(db, ip, "repeated failed login")
        return fail("invalid_credentials", "email or password incorrect", status_code=401)

    if user.status == "deactivated":
        grace_deadline = user.deactivated_at + timedelta(days=settings.deactivation_grace_days)
        if datetime.now(timezone.utc) <= grace_deadline:
            user.status = "active"
            user.is_active = True
            user.deactivated_at = None
        else:
            return fail("account_deleted", "account deactivation grace period expired", status_code=410)

    if not user.is_active:
        return fail("account_disabled", "account is disabled", status_code=403)

    user.failed_login_count = 0
    user.locked_until = None
    await db.commit()

    ua = request.headers.get("user-agent", "")
    risk = await assess_risk(str(user.id), ip, ua)

    if user.mfa_enabled or (risk["requires_step_up"] and user.email_verified):
        mfa_token = await create_mfa_session(str(user.id), str(user.tenant_id), ip, ua)
        return ok({"mfa_required": True, "mfa_token": mfa_token, "reason": "mfa" if user.mfa_enabled else "new_location"})

    access, refresh = await issue_tokens(db, user, request)

    if risk["is_new_context"] and user.email_verified:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        subject, html = new_device_login_tpl(ip, ua, now_str)
        send_email_task.delay(user.email, subject, html)
        await publish_event(f"sse_user:{user.id}", {"type": "security_alert", "message": "new login detected", "ip": ip, "geo": risk["geo"], "time": now_str})

    return ok({"access_token": access, "refresh_token": refresh, "user": {"id": str(user.id), "email": user.email, "email_verified": user.email_verified}})

@router.post("/refresh")
async def refresh_token(body: RefreshRequest, request: Request, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        return fail("invalid_token", "refresh token invalid or expired", status_code=401)

    if payload.get("type") != "refresh" or payload.get("tenant_id") != str(tenant.id):
        return fail("invalid_token", "refresh token invalid", status_code=401)

    jti = payload["jti"]
    family_id = payload["family_id"]

    blacklisted = await redis.get(f"bl:{jti}")
    if blacklisted:
        await redis.set(f"revoke_family:{family_id}", "1", ex=60 * 60 * 24 * 30)
        result = await db.execute(select(Session).where(Session.family_id == family_id))
        for s in result.scalars().all():
            s.revoked = True
        await db.commit()
        return fail("token_reuse_detected", "session family revoked", status_code=401)

    result = await db.execute(select(Session).where(Session.refresh_token_id == jti, Session.family_id == family_id))
    session = result.scalar_one_or_none()
    if not session or session.revoked:
        return fail("invalid_token", "session not found or revoked", status_code=401)

    await redis.set(f"bl:{jti}", "1", ex=60 * 60 * 24 * settings_refresh_days())

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return fail("user_not_found", "user not found or inactive", status_code=401)

    session.revoked = True
    await db.commit()

    access, new_refresh = await issue_tokens(db, user, request, family_id=family_id)
    return ok({"access_token": access, "refresh_token": new_refresh})

@router.post("/logout")
async def logout(body: LogoutRequest, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        return ok({"message": "logged out"})

    jti = payload.get("jti")
    if jti:
        await redis.set(f"bl:{jti}", "1", ex=60 * 60 * 24 * 7)
        result = await db.execute(select(Session).where(Session.refresh_token_id == jti))
        session = result.scalar_one_or_none()
        if session:
            session.revoked = True
            await db.commit()
    return ok({"message": "logged out"})

def settings_refresh_days():
    from app.config import settings
    return settings.refresh_token_expire_days