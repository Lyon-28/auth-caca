from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.router import auth, tenant, health, verify, session, mfa, passwordless, oauth, org, admin, platform, terms, profile, db_admin
from app.response import fail

app = FastAPI(title="Caca Auth", version="0.1.0")

app.mount("/static", StaticFiles(directory=settings.local_storage_path), name="static")

app.mount("/admin", StaticFiles(directory="public/admin", html=True), name="admin-ui")
app.mount("/docs-ui", StaticFiles(directory="public/docs", html=True), name="docs-ui")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return fail(detail.get("code", "error"), detail.get("message", "error"), detail.get("details"), status_code=exc.status_code)
    return fail("error", str(detail), status_code=exc.status_code)

app.include_router(auth.router)
app.include_router(tenant.router)
app.include_router(health.router)
app.include_router(verify.router)
app.include_router(session.router)
app.include_router(mfa.router)
app.include_router(passwordless.router)
app.include_router(oauth.router)
app.include_router(org.router)
app.include_router(admin.router)
app.include_router(platform.router)
app.include_router(terms.router)
app.include_router(profile.router)
app.include_router(db_admin.router)