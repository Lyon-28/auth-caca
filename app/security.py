import uuid
import uuid as uuidlib
import hmac
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError
from app.redis_client import redis
from app.config import settings

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False

def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)

def generate_tenant_keys() -> tuple[str, str]:
    return f"caca-sk_{uuid.uuid4().hex}{uuid.uuid4().hex}", f"caca-pk_{uuid.uuid4().hex}"

def create_access_token(user_id: str, tenant_id: str, scopes: list[str] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "access",
        "scopes": scopes or ["read:profile", "write:data"],
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_refresh_token(user_id: str, tenant_id: str, jti: str, family_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "refresh",
        "jti": jti,
        "family_id": family_id,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise ValueError("invalid_token")
        
def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()
    
async def create_mfa_session(user_id: str, tenant_id: str, ip: str, ua: str) -> str:
    mfa_token = uuidlib.uuid4().hex
    await redis.hset(f"mfa_session:{mfa_token}", mapping={"user_id": user_id, "tenant_id": tenant_id, "ip": ip, "ua": ua, "verified": "0"})
    await redis.expire(f"mfa_session:{mfa_token}", settings.mfa_token_ttl_seconds)
    return mfa_token

async def get_mfa_session(mfa_token: str) -> dict | None:
    data = await redis.hgetall(f"mfa_session:{mfa_token}")
    return data or None