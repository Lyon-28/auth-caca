from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Organization, OrgMember, User
from app.deps import get_current_user
from app.authz import get_member_role, require_role
from app.response import ok, fail
from pydantic import BaseModel

router = APIRouter(prefix="/orgs", tags=["organizations"])

class OrgCreate(BaseModel):
    name: str

class MemberInvite(BaseModel):
    user_id: str
    role: str = "member"

class ImpersonateRequest(BaseModel):
    target_user_id: str

@router.post("")
async def create_org(body: OrgCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org = Organization(tenant_id=user.tenant_id, name=body.name, owner_id=user.id)
    db.add(org)
    await db.flush()
    db.add(OrgMember(org_id=org.id, user_id=user.id, role="owner"))
    await db.commit()
    return ok({"id": str(org.id), "name": org.name}, status_code=201)

@router.get("/{org_id}/members")
async def list_members(org_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await get_member_role(db, org_id, user.id)
    if not role:
        return fail("forbidden", "not a member of this organization", status_code=403)
    result = await db.execute(select(OrgMember).where(OrgMember.org_id == org_id))
    members = result.scalars().all()
    return ok({"members": [{"user_id": str(m.user_id), "role": m.role} for m in members]})

@router.post("/{org_id}/members")
async def invite_member(org_id: str, body: MemberInvite, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await get_member_role(db, org_id, user.id)
    await require_role("admin")(role)
    db.add(OrgMember(org_id=org_id, user_id=body.user_id, role=body.role))
    await db.commit()
    return ok({"message": "member added"}, status_code=201)

@router.delete("/{org_id}/members/{target_user_id}")
async def remove_member(org_id: str, target_user_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await get_member_role(db, org_id, user.id)
    await require_role("admin")(role)
    result = await db.execute(select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == target_user_id))
    member = result.scalar_one_or_none()
    if not member:
        return fail("not_found", "member not found", status_code=404)
    await db.delete(member)
    await db.commit()
    return ok({"message": "member removed"})

@router.post("/{org_id}/impersonate")
async def impersonate(org_id: str, body: ImpersonateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await get_member_role(db, org_id, user.id)
    await require_role("owner")(role)
    from app.router.auth import issue_tokens
    from fastapi import Request
    result = await db.execute(select(User).where(User.id == body.target_user_id))
    target = result.scalar_one_or_none()
    if not target:
        return fail("not_found", "target user not found", status_code=404)
    from app.security import create_access_token
    access = create_access_token(str(target.id), str(target.tenant_id), scopes=["read:profile", "impersonated"])
    return ok({"access_token": access, "impersonating": str(target.id), "by": str(user.id)})