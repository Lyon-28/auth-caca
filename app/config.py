from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: str = "development"
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    resend_api_key: str | None = None
    brevo_api_key: str | None = None
    mailjet_api_key: str | None = None
    mailjet_secret_key: str | None = None
    smtp_gmail_user: str | None = None
    smtp_gmail_password: str | None = None
    mailgun_api_key: str | None = None
    mailgun_domain: str | None = None
    sendgrid_api_key: str | None = None
    firebase_api_key: str | None = None
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    ntfy_topic_url: str | None = None
    gotify_url: str | None = None
    gotify_token: str | None = None
    apprise_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    mail_from: str = "noreply@caca-auth.dev"
    frontend_url: str = "http://localhost:3000"
    celery_broker_url: str
    
    turnstile_secret_key: str | None = None
    login_fail_threshold: int = 5
    login_fail_window_seconds: int = 900
    lockout_duration_seconds: int = 1800
    ip_blacklist_threshold: int = 20
    ip_blacklist_window_seconds: int = 600
    hibp_enabled: bool = True
    
    zenziva_userkey: str | None = None
    zenziva_passkey: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from: str | None = None
    vonage_api_key: str | None = None
    vonage_api_secret: str | None = None
    termii_api_key: str | None = None
    fonnte_token: str | None = None
    wablas_token: str | None = None
    messagebird_api_key: str | None = None
    whatsapp_cloud_token: str | None = None
    whatsapp_cloud_phone_id: str | None = None
    textbee_api_key: str | None = None
    textbee_device_id: str | None = None

    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Caca Auth"
    webauthn_origin: str = "http://localhost:3000"

    mfa_token_ttl_seconds: int = 300
    otp_ttl_seconds: int = 300
    magic_link_ttl_seconds: int = 900
    
    google_client_id: str | None = None
    google_client_secret: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    apple_client_id: str | None = None
    apple_client_secret: str | None = None
    facebook_client_id: str | None = None
    facebook_client_secret: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    twitter_client_id: str | None = None
    twitter_client_secret: str | None = None
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = None
    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    instagram_client_id: str | None = None
    instagram_client_secret: str | None = None
    oauth_redirect_base: str = "http://localhost:8000/auth/oauth"
    geoip_provider_url: str = "https://ipapi.co"
    
    log_level: str = "INFO"
    platform_admin_emails: str = ""
    
    supabase_storage_bucket: str = "avatars"
    imagekit_private_key: str | None = None
    imagekit_public_key: str | None = None
    imagekit_url_endpoint: str | None = None
    imgbb_api_key: str | None = None
    github_storage_token: str | None = None
    github_storage_repo: str | None = None
    github_storage_branch: str = "main"
    local_storage_path: str = "/mnt/storage"
    local_storage_public_url: str = "http://localhost:8000/static"
    avatar_min_bytes: int = 512000
    avatar_max_bytes: int = 5242880
    deactivation_grace_days: int = 30

    webhook_secret: str = "change_this_webhook_secret"
    
    class Config:
        env_file = ".env"

settings = Settings()