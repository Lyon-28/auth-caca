from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User, Tenant, Token
from app.schemas import (
    ResendVerificationRequest, VerifyEmailRequest, ForgotPasswordRequest,
    ResetPasswordRequest, ChangeEmailRequest, ChangeEmailConfirm,
)
from app.security import generate_raw_token, hash_token, hash_password, constant_time_compare
from app.response import ok, fail
from app.deps import get_tenant_from_api_key, get_current_user
from app.notify.templates import verify_email_tpl, reset_password_tpl, password_changed_tpl, change_email_tpl
from app.tasks import send_email_task
from app.config import settings
from app.rate_limit import rate_limiter

router = APIRouter(prefix="/auth", tags=["verify"])

async def _issue_token(db: AsyncSession, user: User, type_: str, expires_minutes: int, payload: str | None = None) -> str:
    raw = generate_raw_token()
    token = Token(
        user_id=user.id, tenant_id=user.tenant_id, type=type_,
        token_hash=hash_token(raw), payload=payload,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    )
    db.add(token)
    await db.commit()
    return raw

async def _consume_token(db: AsyncSession, raw_token: str, type_: str, tenant_id) -> Token | None:
    result = await db.execute(
        select(Token).where(Token.token_hash == hash_token(raw_token), Token.type == type_, Token.tenant_id == tenant_id, Token.used == False)
    )
    token = result.scalar_one_or_none()
    if not token:
        return None
    if token.expires_at < datetime.now(timezone.utc):
        return None
    token.used = True
    await db.commit()
    return token

@router.post("/verify-email/resend", dependencies=[Depends(rate_limiter("resend_verify", 5, 3600))])
async def resend_verification(body: ResendVerificationRequest, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user or user.email_verified:
        return ok({"message": "if the account exists, a verification email has been sent"})

    raw = await _issue_token(db, user, "verify_email", 60 * 24)
    link = f"{settings.frontend_url}/verify-email?token={raw}"
    subject, html = verify_email_tpl(link)
    send_email_task.delay(user.email, subject, html)
    return ok({"message": "if the account exists, a verification email has been sent"})

@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    token = await _consume_token(db, body.token, "verify_email", tenant.id)
    if not token:
        return fail("invalid_token", "verification token invalid or expired", status_code=400)

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("user_not_found", "user not found", status_code=404)

    user.email_verified = True
    await db.commit()
    return ok({"message": "email verified"})

@router.post("/forgot-password", dependencies=[Depends(rate_limiter("forgot_password", 5, 3600))])
async def forgot_password(body: ForgotPasswordRequest, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if user and user.password_hash:
        raw = await _issue_token(db, user, "reset_password", 60)
        link = f"{settings.frontend_url}/reset-password?token={raw}"
        subject, html = reset_password_tpl(link)
        send_email_task.delay(user.email, subject, html)
    return ok({"message": "if the account exists, a reset link has been sent"})

@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    token = await _consume_token(db, body.token, "reset_password", tenant.id)
    if not token:
        return fail("invalid_token", "reset token invalid or expired", status_code=400)

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("user_not_found", "user not found", status_code=404)

    user.password_hash = hash_password(body.new_password)
    await db.commit()

    subject, html = password_changed_tpl()
    send_email_task.delay(user.email, subject, html)
    return ok({"message": "password has been reset"})

@router.post("/change-email/request")
async def change_email_request(body: ChangeEmailRequest, tenant=Depends(get_tenant_from_api_key), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.new_email, User.tenant_id == tenant.id))
    if existing.scalar_one_or_none():
        return fail("email_taken", "email already in use", status_code=409)

    raw = await _issue_token(db, user, "change_email", 60, payload=body.new_email)
    link = f"{settings.frontend_url}/confirm-email-change?token={raw}"
    subject, html = change_email_tpl(link, body.new_email)
    send_email_task.delay(user.email, subject, html)
    send_email_task.delay(body.new_email, subject, html)
    return ok({"message": "confirmation sent to old and new email"})

@router.post("/change-email/confirm")
async def change_email_confirm(body: ChangeEmailConfirm, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    token = await _consume_token(db, body.token, "change_email", tenant.id)
    if not token or not token.payload:
        return fail("invalid_token", "token invalid or expired", status_code=400)

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("user_not_found", "user not found", status_code=404)

    user.email = token.payload
    user.email_verified = True
    await db.commit()
    return ok({"message": "email changed", "email": user.email})