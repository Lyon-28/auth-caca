from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, AuditLog, Session

async def compute_metrics(db: AsyncSession, tenant_id):
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)

    dau = await db.execute(select(func.count(func.distinct(AuditLog.user_id))).where(AuditLog.tenant_id == tenant_id, AuditLog.action == "login_success", AuditLog.created_at >= day_ago))
    mau = await db.execute(select(func.count(func.distinct(AuditLog.user_id))).where(AuditLog.tenant_id == tenant_id, AuditLog.action == "login_success", AuditLog.created_at >= month_ago))

    total_users = await db.execute(select(func.count(User.id)).where(User.tenant_id == tenant_id))
    total_signups_30d = await db.execute(select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id, AuditLog.action == "user_registered", AuditLog.created_at >= month_ago))

    login_success = await db.execute(select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id, AuditLog.action == "login_success", AuditLog.created_at >= day_ago))
    login_failed = await db.execute(select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id, AuditLog.action == "login_failed", AuditLog.created_at >= day_ago))

    success_count = login_success.scalar() or 0
    failed_count = login_failed.scalar() or 0
    total_attempts = success_count + failed_count

    return {
        "dau": dau.scalar() or 0,
        "mau": mau.scalar() or 0,
        "total_users": total_users.scalar() or 0,
        "signups_30d": total_signups_30d.scalar() or 0,
        "login_success_rate": round(success_count / total_attempts, 4) if total_attempts else None,
        "login_failure_rate": round(failed_count / total_attempts, 4) if total_attempts else None,
        "login_attempts_24h": total_attempts,
    }
    
    


# TAMBAHAN 
"""
 Metrics "auth method terpopuler" dan "avg session duration" butuh kolom tambahan (`login_method` di audit meta, `ended_at` di Session) — ditambahkan langsung di bawah lewat query terhadap `metadata_json` dan `last_active_at - created_at`, tanpa perlu migrasi besar:
"""
async def compute_method_breakdown(db: AsyncSession, tenant_id):
    result = await db.execute(select(AuditLog.metadata_json).where(AuditLog.tenant_id == tenant_id, AuditLog.action == "login_success"))
    import json
    from collections import Counter
    counter = Counter()
    for row in result.scalars().all():
        try:
            meta = json.loads(row) if row else {}
            counter[meta.get("method", "password")] += 1
        except Exception:
            continue
    return dict(counter)

async def compute_avg_session_duration(db: AsyncSession, tenant_id):
    result = await db.execute(select(Session.created_at, Session.last_active_at).where(Session.tenant_id == tenant_id))
    rows = result.all()
    if not rows:
        return None
    total = sum((r.last_active_at - r.created_at).total_seconds() for r in rows)
    return round(total / len(rows), 2)