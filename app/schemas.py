from pydantic import BaseModel, EmailStr, field_validator
import re

class TenantRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class TenantLogin(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("password must be at least 8 chars with letters and numbers")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str
    
class ResendVerificationRequest(BaseModel):
    email: EmailStr

class VerifyEmailRequest(BaseModel):
    token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("password must be at least 8 chars with letters and numbers")
        return v

class ChangeEmailRequest(BaseModel):
    new_email: EmailStr

class ChangeEmailConfirm(BaseModel):
    token: str
    
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_token: str | None = None

    @field_validator("password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("password must be at least 8 chars with letters and numbers")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_token: str | None = None
    
class TotpConfirm(BaseModel):
    code: str

class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str

class MfaOtpSendRequest(BaseModel):
    mfa_token: str
    method: str

class PushApproveRequest(BaseModel):
    challenge_id: str
    approve: bool

class MagicLinkRequest(BaseModel):
    email: EmailStr

class MagicLinkVerify(BaseModel):
    token: str

class OtpLoginRequest(BaseModel):
    phone: str

class OtpLoginVerify(BaseModel):
    phone: str
    code: str

class WebauthnVerifyRequest(BaseModel):
    credential: dict
    challenge_id: str
    
class UpdateProfile(BaseModel):
    name: str | None = None
    bio: str | None = None
    birthdate: str | None = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("password must be at least 8 chars with letters and numbers")
        return v

class UpdatePreferences(BaseModel):
    language: str | None = None
    timezone: str | None = None
    notify_email: bool | None = None
    notify_sms: bool | None = None
    profile_visibility: str | None = None