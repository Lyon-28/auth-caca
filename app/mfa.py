import secrets
import json
import hashlib
import pyotp
from app.security import hash_token

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="Caca Auth")

def verify_totp(secret: str, code: str) -> bool:
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)

def generate_backup_codes(count: int = 10) -> list[str]:
    return [secrets.token_hex(4) for _ in range(count)]

def hash_backup_codes(codes: list[str]) -> str:
    return json.dumps([hashlib.sha256(c.encode()).hexdigest() for c in codes])

def verify_and_consume_backup_code(stored_json: str, code: str) -> str | None:
    hashes = json.loads(stored_json)
    target = hashlib.sha256(code.encode()).hexdigest()
    if target in hashes:
        hashes.remove(target)
        return json.dumps(hashes)
    return None

def generate_otp_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"