from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import OrgMember, Resource

ROLE_RANK = {"owner": 5, "admin": 4, "manager": 3, "member": 2, "guest": 1}

async def get_member_role(db: AsyncSession, org_id, user_id) -> str | None:
    result = await db.execute(select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == user_id))
    member = result.scalar_one_or_none()
    return member.role if member else None

def require_role(min_role: str):
    async def checker(role: str | None):
        if not role or ROLE_RANK.get(role, 0) < ROLE_RANK.get(min_role, 0):
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": f"requires role >= {min_role}"})
    return checker

def check_abac(user, resource_attrs: dict, action: str) -> bool:
    if action == "delete" and resource_attrs.get("locked"):
        return False
    if action == "write" and not user.email_verified and resource_attrs.get("sensitive"):
        return False
    return True

async def check_ownership(db: AsyncSession, resource_id, user_id) -> bool:
    result = await db.execute(select(Resource).where(Resource.id == resource_id))
    resource = result.scalar_one_or_none()
    return bool(resource and resource.owner_id == user_id)

def has_scope(token_scopes: list[str], required: str) -> bool:
    return required in token_scopes or "*" in token_scopes