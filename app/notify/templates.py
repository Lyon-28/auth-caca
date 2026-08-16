def verify_email_tpl(link: str) -> tuple[str, str]:
    subject = "Verify your email"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2>Verify your email</h2>
      <p>Click the button below to verify your email. This link expires in 24 hours.</p>
      <a href="{link}" style="background:#111;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;display:inline-block">Verify Email</a>
      <p style="color:#888;font-size:12px">If you didn't request this, ignore this email.</p>
    </div>
    """
    return subject, html

def reset_password_tpl(link: str) -> tuple[str, str]:
    subject = "Reset your password"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2>Reset your password</h2>
      <p>Click the button below to reset your password. This link expires in 1 hour.</p>
      <a href="{link}" style="background:#111;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;display:inline-block">Reset Password</a>
      <p style="color:#888;font-size:12px">If you didn't request this, ignore this email.</p>
    </div>
    """
    return subject, html

def password_changed_tpl() -> tuple[str, str]:
    return "Your password was changed", "<p>Your password was just changed. If this wasn't you, contact support immediately.</p>"

def change_email_tpl(link: str, target: str) -> tuple[str, str]:
    subject = "Confirm email change"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2>Confirm email change</h2>
      <p>Confirm changing your account email to <b>{target}</b>. This link expires in 1 hour.</p>
      <a href="{link}" style="background:#111;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;display:inline-block">Confirm</a>
    </div>
    """
    return subject, html

def welcome_tpl(email: str) -> tuple[str, str]:
    return "Welcome to Caca", f"<p>Welcome, {email}! Your account has been created.</p>"

def new_device_login_tpl(ip: str, ua: str, time_str: str) -> tuple[str, str]:
    subject = "New login detected"
    html = f"<p>New login from IP {ip}, device {ua}, at {time_str}. If this wasn't you, secure your account.</p>"
    return subject, html