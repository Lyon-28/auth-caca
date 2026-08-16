import time
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, engine
from app.deps import get_platform_admin
from app.response import ok, fail

router = APIRouter(prefix="/platform/db", tags=["db-admin"])

@router.get("/health")
async def db_health(db: AsyncSession = Depends(get_db)):
    start = time.perf_counter()
    try:
        await db.execute(text("select 1"))
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return ok({"status": "up", "response_time_ms": elapsed_ms})
    except Exception as e:
        return fail("db_down", str(e), status_code=500)

@router.get("/pool")
async def pool_status(admin=Depends(get_platform_admin)):
    pool = engine.pool
    return ok({
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    })

@router.get("/schema")
async def schema_info(admin=Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("""
        select table_name, column_name, data_type, is_nullable
        from information_schema.columns
        where table_schema = 'public'
        order by table_name, ordinal_position
    """))
    rows = result.fetchall()
    tables = {}
    for table_name, column_name, data_type, is_nullable in rows:
        tables.setdefault(table_name, []).append({"column": column_name, "type": data_type, "nullable": is_nullable == "YES"})
    return ok({"tables": tables})

@router.get("/table-stats")
async def table_stats(admin=Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("""
        select relname as table_name, n_live_tup as row_estimate,
               pg_size_pretty(pg_total_relation_size(relid)) as size
        from pg_stat_user_tables
        order by n_live_tup desc
    """))
    rows = result.fetchall()
    return ok({"tables": [{"name": r[0], "row_estimate": r[1], "size": r[2]} for r in rows]})

@router.get("/slow-queries")
async def slow_queries(admin=Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("""
            select query, calls, mean_exec_time, max_exec_time
            from pg_stat_statements order by mean_exec_time desc limit 20
        """))
        rows = result.fetchall()
        return ok({"queries": [{"query": r[0][:200], "calls": r[1], "mean_ms": round(r[2], 2), "max_ms": round(r[3], 2)} for r in rows]})
    except Exception:
        return fail("extension_missing", "pg_stat_statements extension not enabled on this database", status_code=501)