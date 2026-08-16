import json
from app.database import SessionLocal
from app.models import AuditLog
from app.logger import log

async def record_audit(tenant_id, user_id, action: str, ip: str | None = None, ua: str | None = None, meta: dict | None = None):
    async with SessionLocal() as db:
        entry = AuditLog(
            tenant_id=tenant_id, user_id=user_id, action=action,
            ip_address=ip, user_agent=ua, metadata_json=json.dumps(meta or {}),
        )
        db.add(entry)
        await db.commit()
    log("info", f"audit:{action}", tenant_id=str(tenant_id) if tenant_id else None, user_id=str(user_id) if user_id else None, ip=ip, meta=meta or {})