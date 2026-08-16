from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Tenant
from app.schemas import TenantRegister, TenantLogin
from app.security import hash_password, verify_password, generate_tenant_keys
from app.response import ok, fail

router = APIRouter(prefix="/tenant", tags=["tenant"])

@router.post("/register")
async def register_tenant(body: TenantRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Tenant).where(Tenant.email == body.email))
    if existing.scalar_one_or_none():
        return fail("tenant_exists", "email already registered", status_code=409)

    sk, pk = generate_tenant_keys()
    tenant = Tenant(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        secret_key=sk,
        public_key=pk,
    )
    db.add(tenant)
    await db.commit()
    return ok({"tenant_id": str(tenant.id), "secret_key": sk, "public_key": pk}, status_code=201)

@router.post("/login")
async def login_tenant(body: TenantLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tenant).where(Tenant.email == body.email))
    tenant = result.scalar_one_or_none()
    if not tenant or not verify_password(body.password, tenant.password_hash):
        return fail("invalid_credentials", "email or password incorrect", status_code=401)
    admin_token = create_access_token(str(tenant.id), str(tenant.id), scopes=["platform_admin"] if tenant.is_platform_admin else ["tenant"])
    return ok({"tenant_id": str(tenant.id), "secret_key": tenant.secret_key, "public_key": tenant.public_key, "admin_token": admin_token})