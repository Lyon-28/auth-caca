from authlib.integrations.httpx_client import AsyncOAuth2Client
import httpx
from app.config import settings

PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
        "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
        "client_id": settings.github_client_id, "client_secret": settings.github_client_secret,
    },
    "apple": {
        "auth_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        "userinfo_url": None,
        "scope": "name email",
        "client_id": settings.apple_client_id, "client_secret": settings.apple_client_secret,
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/me?fields=id,name,email",
        "scope": "email public_profile",
        "client_id": settings.facebook_client_id, "client_secret": settings.facebook_client_secret,
    },
    "microsoft": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/oidc/userinfo",
        "scope": "openid email profile",
        "client_id": settings.microsoft_client_id, "client_secret": settings.microsoft_client_secret,
    },
    "twitter": {
        "auth_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "userinfo_url": "https://api.twitter.com/2/users/me",
        "scope": "users.read tweet.read",
        "client_id": settings.twitter_client_id, "client_secret": settings.twitter_client_secret,
    },
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "userinfo_url": "https://api.linkedin.com/v2/userinfo",
        "scope": "openid email profile",
        "client_id": settings.linkedin_client_id, "client_secret": settings.linkedin_client_secret,
    },
    "discord": {
        "auth_url": "https://discord.com/oauth2/authorize",
        "token_url": "https://discord.com/api/oauth2/token",
        "userinfo_url": "https://discord.com/api/users/@me",
        "scope": "identify email",
        "client_id": settings.discord_client_id, "client_secret": settings.discord_client_secret,
    },
    "instagram": {
        "auth_url": "https://api.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "userinfo_url": "https://graph.instagram.com/me?fields=id,username",
        "scope": "user_profile",
        "client_id": settings.instagram_client_id, "client_secret": settings.instagram_client_secret,
    },
}

def get_authorize_url(provider: str, state: str) -> str:
    cfg = PROVIDERS[provider]
    redirect_uri = f"{settings.oauth_redirect_base}/{provider}/callback"
    client = AsyncOAuth2Client(cfg["client_id"], cfg["client_secret"], scope=cfg["scope"], redirect_uri=redirect_uri)
    url, _ = client.create_authorization_url(cfg["auth_url"], state=state)
    return url

async def exchange_code(provider: str, code: str) -> dict:
    cfg = PROVIDERS[provider]
    redirect_uri = f"{settings.oauth_redirect_base}/{provider}/callback"
    client = AsyncOAuth2Client(cfg["client_id"], cfg["client_secret"], redirect_uri=redirect_uri)
    token = await client.fetch_token(cfg["token_url"], code=code)
    async with httpx.AsyncClient(timeout=10) as http_client:
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        resp = await http_client.get(cfg["userinfo_url"], headers=headers)
        resp.raise_for_status()
        return resp.json()

def normalize_userinfo(provider: str, raw: dict) -> dict:
    if provider == "google" or provider == "microsoft" or provider == "linkedin":
        return {"id": raw.get("sub"), "email": raw.get("email")}
    if provider == "github":
        return {"id": str(raw.get("id")), "email": raw.get("email")}
    if provider == "facebook":
        return {"id": raw.get("id"), "email": raw.get("email")}
    if provider == "discord":
        return {"id": raw.get("id"), "email": raw.get("email")}
    if provider == "twitter":
        return {"id": raw.get("data", {}).get("id"), "email": None}
    if provider == "instagram":
        return {"id": raw.get("id"), "email": None}
    return {"id": raw.get("id") or raw.get("sub"), "email": raw.get("email")}