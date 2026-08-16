import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User, Tenant, OAuthAccount
from app.deps import get_tenant_from_api_key
from app.oauth import get_authorize_url, exchange_code, normalize_userinfo, PROVIDERS
from app.redis_client import redis
from app.response import fail
from app.config import settings
from app.router.auth import issue_tokens

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])

@router.get("/{provider}/start")
async def oauth_start(provider: str, tenant: Tenant = Depends(get_tenant_from_api_key)):
    if provider not in PROVIDERS:
        return fail("unsupported_provider", "provider not supported", status_code=400)
    state = uuid.uuid4().hex
    await redis.set(f"oauth_state:{state}", str(tenant.id), ex=600)
    url = get_authorize_url(provider, state)
    return RedirectResponse(url)

@router.get("/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str, request: Request, db: AsyncSession = Depends(get_db)):
    tenant_id = await redis.get(f"oauth_state:{state}")
    if not tenant_id:
        return fail("invalid_state", "oauth state invalid or expired", status_code=400)
    await redis.delete(f"oauth_state:{state}")

    raw = await exchange_code(provider, code)
    info = normalize_userinfo(provider, raw)
    provider_user_id = info["id"]
    email = info["email"] or f"{provider_user_id}@{provider}.caca-auth.local"

    result = await db.execute(select(OAuthAccount).where(OAuthAccount.provider == provider, OAuthAccount.provider_user_id == provider_user_id, OAuthAccount.tenant_id == tenant_id))
    oauth_account = result.scalar_one_or_none()

    if oauth_account:
        result = await db.execute(select(User).where(User.id == oauth_account.user_id))
        user = result.scalar_one_or_none()
    else:
        result = await db.execute(select(User).where(User.email == email, User.tenant_id == tenant_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(tenant_id=tenant_id, email=email, password_hash=None, email_verified=True)
            db.add(user)
            await db.flush()
        else:
            user.email_verified = True
        db.add(OAuthAccount(user_id=user.id, tenant_id=tenant_id, provider=provider, provider_user_id=provider_user_id, email=info["email"]))
        await db.commit()

    access, refresh = await issue_tokens(db, user, request)
    redirect = f"{settings.frontend_url}/oauth-callback?access_token={access}&refresh_token={refresh}"
    return RedirectResponse(redirect)