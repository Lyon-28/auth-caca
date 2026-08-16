# Caca Auth

Production-ready multi-tenant Auth-as-a-Service. FastAPI + Neon Postgres + Upstash Redis.

## Setup
1. `cp .env.example .env` and fill in credentials
2. `pip install -r requirements.txt`
3. `alembic upgrade head`
4. `uvicorn app.main:app --reload`
5. Worker: `celery -A app.celery_app worker --loglevel=info`
6. Beat: `celery -A app.celery_app beat --loglevel=info`

## Docs
- Swagger: `/docs`
- Custom docs UI: `/docs-ui`
- Admin dashboard: `/admin`
- OpenAPI JSON (import to Postman): `/openapi.json`

## Testing
`pytest tests/ -v`

## Deploy
- Railway / Vercel / any ASGI-compatible host
- DB: Neon (Postgres) — enable point-in-time recovery in Neon dashboard
- Redis: Upstash
- Set `ENV=production` and rotate `JWT_SECRET`, `WEBHOOK_SECRET` before going live

## Architecture
Dual-token JWT (access 15m / refresh 7d, Bearer-only, no cookies), refresh token rotation with reuse detection, multi-tenant isolation via `tenant_id`, hybrid fallback chains for email/SMS/storage providers.