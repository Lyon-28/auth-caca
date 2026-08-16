from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User, UserPreference
from app.schemas import UpdateProfile, ChangePasswordRequest, UpdatePreferences
from app.deps import get_current_user, require_verified_email
from app.security import hash_password, verify_password
from app.storage import upload_avatar
from app.cache import get_cached_profile, set_cached_profile, invalidate_profile_cache
from app.gdpr import collect_user_data, to_json_bytes, to_csv_bytes
from app.response import ok, fail
from app.config import settings
from app.audit import record_audit
from app.notify.templates import password_changed_tpl
from app.tasks import send_email_task

router = APIRouter(prefix="/profile", tags=["profile"])

def _serialize(user: User) -> dict:
    return {
        "id": str(user.id), "email": user.email, "phone": user.phone,
        "name": user.name, "bio": user.bio, "avatar_url": user.avatar_url,
        "email_verified": user.email_verified, "mfa_enabled": user.mfa_enabled,
        "status": user.status, "created_at": user.created_at.isoformat(),
    }

@router.get("")
async def get_profile(user: User = Depends(get_current_user)):
    cached = await get_cached_profile(str(user.id))
    if cached:
        return ok(cached)
    data = _serialize(user)
    await set_cached_profile(str(user.id), data)
    return ok(data)

@router.patch("")
async def update_profile(body: UpdateProfile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.name is not None:
        user.name = body.name
    if body.bio is not None:
        user.bio = body.bio
    if body.birthdate is not None:
        user.birthdate = datetime.fromisoformat(body.birthdate)
    await db.commit()
    await invalidate_profile_cache(str(user.id))
    return ok(_serialize(user))

@router.post("/avatar")
async def upload_avatar_endpoint(file: UploadFile = File(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    raw = await file.read()
    if len(raw) < settings.avatar_min_bytes or len(raw) > settings.avatar_max_bytes:
        return fail("invalid_size", f"avatar must be between {settings.avatar_min_bytes} and {settings.avatar_max_bytes} bytes", status_code=400)
    try:
        url = await upload_avatar(raw)
    except Exception as e:
        return fail("upload_failed", str(e), status_code=502)
    user.avatar_url = url
    await db.commit()
    await invalidate_profile_cache(str(user.id))
    return ok({"avatar_url": url})

@router.delete("/avatar")
async def delete_avatar(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.avatar_url = None
    await db.commit()
    await invalidate_profile_cache(str(user.id))
    return ok({"message": "avatar removed"})

@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, user: User = Depends(require_verified_email), db: AsyncSession = Depends(get_db)):
    if not user.password_hash or not verify_password(body.old_password, user.password_hash):
        return fail("invalid_password", "old password incorrect", status_code=400)
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    subject, html = password_changed_tpl()
    send_email_task.delay(user.email, subject, html)
    await record_audit(user.tenant_id, user.id, "password_changed")
    return ok({"message": "password changed"})

@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    pref = result.scalar_one_or_none()
    if not pref:
        pref = UserPreference(user_id=user.id)
        db.add(pref)
        await db.commit()
    return ok({
        "language": pref.language, "timezone": pref.timezone,
        "notify_email": pref.notify_email, "notify_sms": pref.notify_sms,
        "profile_visibility": pref.profile_visibility,
    })

@router.patch("/preferences")
async def update_preferences(body: UpdatePreferences, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    pref = result.scalar_one_or_none()
    if not pref:
        pref = UserPreference(user_id=user.id)
        db.add(pref)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pref, field, value)
    await db.commit()
    return ok({"message": "preferences updated"})

@router.get("/export")
async def export_data(format: str = "json", user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = await collect_user_data(db, user)
    if format == "csv":
        return ok({"content": to_csv_bytes(data).decode()}, meta={"format": "csv"})
    return ok(data, meta={"format": "json"})

@router.post("/deactivate")
async def deactivate_account(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.status = "deactivated"
    user.is_active = False
    user.deactivated_at = datetime.now(timezone.utc)
    await db.commit()
    await invalidate_profile_cache(str(user.id))
    await record_audit(user.tenant_id, user.id, "account_deactivated")
    return ok({"message": f"account deactivated, reactivate within {settings.deactivation_grace_days} days or it will be permanently deleted"})

@router.post("/reactivate")
async def reactivate_account(body: dict, tenant=Depends(get_current_user := get_current_user), db: AsyncSession = Depends(get_db)):
    return ok({"message": "use /auth/login to reactivate an account still within grace period"})

@router.delete("")
async def delete_account_hard(confirm: bool = False, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not confirm:
        return fail("confirmation_required", "pass confirm=true to permanently delete your account", status_code=400)
    data = await collect_user_data(db, user)
    user.status = "deleted"
    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    user.email = f"deleted_{user.id}@deleted.caca-auth.local"
    user.phone = None
    user.password_hash = None
    await db.commit()
    await invalidate_profile_cache(str(user.id))
    await record_audit(user.tenant_id, user.id, "account_deleted")
    return ok({"message": "account permanently deleted", "exported_data": data})