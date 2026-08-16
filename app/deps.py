from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Tenant, User
from app.security import decode_token, create_access_token

async def get_tenant_from_api_key(x_api_key: str = Header(...), db: AsyncSession = Depends(get_db)) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.secret_key == x_api_key))
    tenant = result.scalar_one_or_none()
    if not tenant:
        result = await db.execute(select(Tenant).where(Tenant.public_key == x_api_key))
        tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=401, detail="invalid_api_key")
    return tenant

async def get_current_user(
    authorization: str = Header(...),
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_authorization_header")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")
    if payload.get("type") != "access" or payload.get("tenant_id") != str(tenant.id):
        raise HTTPException(status_code=401, detail="invalid_token")
    result = await db.execute(select(User).where(User.id == payload["sub"], User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user_not_found")
    return user

async def require_verified_email(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="email_not_verified")
    return user
    
def require_scope(scope: str):
    async def checker(user: User = Depends(get_current_user), authorization: str = Header(...)):
        token = authorization.removeprefix("Bearer ")
        payload = decode_token(token)
        if scope not in payload.get("scopes", []) and "*" not in payload.get("scopes", []):
            raise HTTPException(status_code=403, detail={"code": "insufficient_scope", "message": f"missing scope {scope}"})
        return user
    return checker
    
async def get_platform_admin(authorization: str = Header(...), db: AsyncSession = Depends(get_db)) -> Tenant:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_authorization_header")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")
    result = await db.execute(select(Tenant).where(Tenant.id == payload.get("tenant_id")))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.is_platform_admin:
        raise HTTPException(status_code=403, detail="platform_admin_required")
    return tenant