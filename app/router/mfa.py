import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import generate_registration_options, verify_registration_response, generate_authentication_options, verify_authentication_response
from webauthn.helpers.structs import PublicKeyCredentialDescriptor
from app.database import get_db
from app.models import User, MfaFactor, WebauthnCredential, Session
from app.schemas import TotpConfirm, MfaVerifyRequest, MfaOtpSendRequest, PushApproveRequest, WebauthnVerifyRequest
from app.deps import get_current_user, get_tenant_from_api_key
from app.security import create_mfa_session, get_mfa_session
from app.mfa import generate_totp_secret, totp_provisioning_uri, verify_totp, generate_backup_codes, hash_backup_codes, verify_and_consume_backup_code, generate_otp_code
from app.response import ok, fail
from app.redis_client import redis
from app.sse import sse_response, publish_event
from app.tasks import send_email_task, send_sms_task
from app.notify.templates import verify_email_tpl
from app.config import settings
from app.router.auth import issue_tokens

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])

@router.post("/totp/setup")
async def totp_setup(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    secret = generate_totp_secret()
    factor = MfaFactor(user_id=user.id, tenant_id=user.tenant_id, type="totp", secret=secret, confirmed=False)
    db.add(factor)
    await db.commit()
    return ok({"factor_id": str(factor.id), "secret": secret, "otpauth_uri": totp_provisioning_uri(secret, user.email)})

@router.post("/totp/confirm/{factor_id}")
async def totp_confirm(factor_id: str, body: TotpConfirm, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MfaFactor).where(MfaFactor.id == factor_id, MfaFactor.user_id == user.id, MfaFactor.type == "totp"))
    factor = result.scalar_one_or_none()
    if not factor or not verify_totp(factor.secret, body.code):
        return fail("invalid_code", "invalid totp code", status_code=400)
    factor.confirmed = True
    user.mfa_enabled = True
    await db.commit()
    return ok({"message": "totp enabled"})

@router.post("/backup-codes/generate")
async def backup_codes_generate(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    codes = generate_backup_codes()
    result = await db.execute(select(MfaFactor).where(MfaFactor.user_id == user.id, MfaFactor.type == "backup_codes"))
    factor = result.scalar_one_or_none()
    if factor:
        factor.secret = hash_backup_codes(codes)
    else:
        db.add(MfaFactor(user_id=user.id, tenant_id=user.tenant_id, type="backup_codes", secret=hash_backup_codes(codes), confirmed=True))
    await db.commit()
    return ok({"codes": codes})

@router.delete("/factors/{factor_id}")
async def disable_factor(factor_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MfaFactor).where(MfaFactor.id == factor_id, MfaFactor.user_id == user.id))
    factor = result.scalar_one_or_none()
    if not factor:
        return fail("not_found", "factor not found", status_code=404)
    await db.delete(factor)
    remaining = await db.execute(select(MfaFactor).where(MfaFactor.user_id == user.id, MfaFactor.confirmed == True))
    if not remaining.scalars().first():
        user.mfa_enabled = False
    await db.commit()
    return ok({"message": "factor disabled"})

async def _resolve_mfa_session(mfa_token: str, db: AsyncSession):
    data = await get_mfa_session(mfa_token)
    if not data:
        return None, None
    result = await db.execute(select(User).where(User.id == data["user_id"]))
    user = result.scalar_one_or_none()
    return user, data

@router.post("/totp/verify")
async def totp_verify(body: MfaVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user, data = await _resolve_mfa_session(body.mfa_token, db)
    if not user:
        return fail("invalid_mfa_session", "mfa session expired", status_code=401)
    result = await db.execute(select(MfaFactor).where(MfaFactor.user_id == user.id, MfaFactor.type == "totp", MfaFactor.confirmed == True))
    factor = result.scalar_one_or_none()
    if not factor or not verify_totp(factor.secret, body.code):
        return fail("invalid_code", "invalid totp code", status_code=400)
    access, refresh = await issue_tokens(db, user, request)
    await redis.delete(f"mfa_session:{body.mfa_token}")
    return ok({"access_token": access, "refresh_token": refresh})

@router.post("/backup-code/verify")
async def backup_code_verify(body: MfaVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user, data = await _resolve_mfa_session(body.mfa_token, db)
    if not user:
        return fail("invalid_mfa_session", "mfa session expired", status_code=401)
    result = await db.execute(select(MfaFactor).where(MfaFactor.user_id == user.id, MfaFactor.type == "backup_codes"))
    factor = result.scalar_one_or_none()
    if not factor:
        return fail("not_configured", "backup codes not set up", status_code=400)
    new_hashes = verify_and_consume_backup_code(factor.secret, body.code)
    if new_hashes is None:
        return fail("invalid_code", "invalid backup code", status_code=400)
    factor.secret = new_hashes
    access, refresh = await issue_tokens(db, user, request)
    await redis.delete(f"mfa_session:{body.mfa_token}")
    await db.commit()
    return ok({"access_token": access, "refresh_token": refresh})

@router.post("/otp/send")
async def mfa_otp_send(body: MfaOtpSendRequest, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    data = await get_mfa_session(body.mfa_token)
    if not data:
        return fail("invalid_mfa_session", "mfa session expired", status_code=401)
    result = await db.execute(select(User).where(User.id == data["user_id"]))
    user = result.scalar_one_or_none()
    code = generate_otp_code()
    await redis.set(f"mfa_otp:{body.mfa_token}", code, ex=settings.otp_ttl_seconds)
    if body.method == "sms" and user.phone:
        send_sms_task.delay(user.phone, f"Your Caca Auth verification code is {code}")
    else:
        subject, html = f"Your verification code", f"<p>Your verification code is <b>{code}</b>, valid {settings.otp_ttl_seconds // 60} minutes.</p>"
        send_email_task.delay(user.email, subject, html)
    return ok({"message": "otp sent"})

@router.post("/otp/verify")
async def mfa_otp_verify(body: MfaVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user, data = await _resolve_mfa_session(body.mfa_token, db)
    if not user:
        return fail("invalid_mfa_session", "mfa session expired", status_code=401)
    stored = await redis.get(f"mfa_otp:{body.mfa_token}")
    if not stored or stored != body.code:
        return fail("invalid_code", "invalid or expired otp", status_code=400)
    await redis.delete(f"mfa_otp:{body.mfa_token}")
    access, refresh = await issue_tokens(db, user, request)
    await redis.delete(f"mfa_session:{body.mfa_token}")
    return ok({"access_token": access, "refresh_token": refresh})

@router.post("/push/start")
async def push_start(body: dict, db: AsyncSession = Depends(get_db)):
    mfa_token = body.get("mfa_token")
    data = await get_mfa_session(mfa_token)
    if not data:
        return fail("invalid_mfa_session", "mfa session expired", status_code=401)
    result = await db.execute(select(Session).where(Session.user_id == data["user_id"], Session.revoked == False))
    active = result.scalars().first()
    if not active:
        return fail("no_active_device", "no active device to approve, use another mfa method", status_code=409)
    challenge_id = uuid.uuid4().hex
    await redis.set(f"push_challenge:{challenge_id}", json.dumps({"mfa_token": mfa_token, "status": "pending"}), ex=120)
    await publish_event(f"sse_user:{data['user_id']}", {"type": "push_mfa_request", "challenge_id": challenge_id})
    return ok({"challenge_id": challenge_id, "message": "approval request sent to active device"})

@router.get("/push/stream")
async def push_stream(user: User = Depends(get_current_user)):
    return sse_response(f"sse_user:{user.id}")

@router.post("/push/approve")
async def push_approve(body: PushApproveRequest, user: User = Depends(get_current_user)):
    raw = await redis.get(f"push_challenge:{body.challenge_id}")
    if not raw:
        return fail("expired", "challenge expired", status_code=400)
    data = json.loads(raw)
    data["status"] = "approved" if body.approve else "denied"
    await redis.set(f"push_challenge:{body.challenge_id}", json.dumps(data), ex=60)
    return ok({"message": data["status"]})

@router.post("/push/status")
async def push_status(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
    challenge_id = body.get("challenge_id")
    raw = await redis.get(f"push_challenge:{challenge_id}")
    if not raw:
        return fail("expired", "challenge expired", status_code=400)
    data = json.loads(raw)
    if data["status"] == "pending":
        return ok({"status": "pending"})
    if data["status"] == "denied":
        return fail("denied", "login denied", status_code=401)
    user, _ = await _resolve_mfa_session(data["mfa_token"], db)
    access, refresh = await issue_tokens(db, user, request)
    await redis.delete(f"mfa_session:{data['mfa_token']}")
    return ok({"access_token": access, "refresh_token": refresh})

@router.post("/webauthn/register/options")
async def webauthn_register_options(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WebauthnCredential).where(WebauthnCredential.user_id == user.id))
    existing = [PublicKeyCredentialDescriptor(id=bytes.fromhex(c.credential_id)) for c in result.scalars().all()]
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id, rp_name=settings.webauthn_rp_name,
        user_id=str(user.id).encode(), user_name=user.email, exclude_credentials=existing,
    )
    await redis.set(f"webauthn_reg:{user.id}", options.challenge.hex(), ex=300)
    return ok({"options": json.loads(options.model_dump_json())})

@router.post("/webauthn/register/verify")
async def webauthn_register_verify(body: WebauthnVerifyRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    challenge_hex = await redis.get(f"webauthn_reg:{user.id}")
    if not challenge_hex:
        return fail("expired", "registration challenge expired", status_code=400)
    verification = verify_registration_response(
        credential=body.credential, expected_challenge=bytes.fromhex(challenge_hex),
        expected_origin=settings.webauthn_origin, expected_rp_id=settings.webauthn_rp_id,
    )
    db.add(WebauthnCredential(
        user_id=user.id, tenant_id=user.tenant_id,
        credential_id=verification.credential_id.hex(), public_key=verification.credential_public_key.hex(),
        sign_count=verification.sign_count,
    ))
    user.mfa_enabled = True
    await db.commit()
    await redis.delete(f"webauthn_reg:{user.id}")
    return ok({"message": "passkey registered"})

@router.post("/webauthn/login/options")
async def webauthn_login_options(body: dict, tenant=Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.get("email"), User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("not_found", "user not found", status_code=404)
    creds = await db.execute(select(WebauthnCredential).where(WebauthnCredential.user_id == user.id))
    allow = [PublicKeyCredentialDescriptor(id=bytes.fromhex(c.credential_id)) for c in creds.scalars().all()]
    options = generate_authentication_options(rp_id=settings.webauthn_rp_id, allow_credentials=allow)
    await redis.set(f"webauthn_auth:{user.id}", options.challenge.hex(), ex=300)
    return ok({"options": json.loads(options.model_dump_json()), "user_id": str(user.id)})

@router.post("/webauthn/login/verify")
async def webauthn_login_verify(body: dict, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = body.get("user_id")
    challenge_hex = await redis.get(f"webauthn_auth:{user_id}")
    if not challenge_hex:
        return fail("expired", "auth challenge expired", status_code=400)
    cred_id = body["credential"]["id"]
    result = await db.execute(select(WebauthnCredential).where(WebauthnCredential.credential_id == cred_id))
    cred = result.scalar_one_or_none()
    if not cred:
        return fail("not_found", "credential not found", status_code=404)
    verification = verify_authentication_response(
        credential=body["credential"], expected_challenge=bytes.fromhex(challenge_hex),
        expected_origin=settings.webauthn_origin, expected_rp_id=settings.webauthn_rp_id,
        credential_public_key=bytes.fromhex(cred.public_key), credential_current_sign_count=cred.sign_count,
    )
    cred.sign_count = verification.new_sign_count
    result = await db.execute(select(User).where(User.id == cred.user_id))
    user = result.scalar_one_or_none()
    access, refresh = await issue_tokens(db, user, request)
    await redis.delete(f"webauthn_auth:{user_id}")
    await db.commit()
    return ok({"access_token": access, "refresh_token": refresh})