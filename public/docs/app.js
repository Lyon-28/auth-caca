const ENDPOINTS = [
  { group: "Auth", method: "POST", path: "/auth/register", desc: "Register a new user with email & password.", body: { email: "user@example.com", password: "Password123" } },
  { group: "Auth", method: "POST", path: "/auth/login", desc: "Login with email & password. Returns tokens or mfa_required.", body: { email: "user@example.com", password: "Password123" } },
  { group: "Auth", method: "POST", path: "/auth/refresh", desc: "Rotate refresh token and get a new access token.", body: { refresh_token: "..." } },
  { group: "Auth", method: "POST", path: "/auth/logout", desc: "Revoke a refresh token / session.", body: { refresh_token: "..." } },
  { group: "Auth", method: "POST", path: "/auth/verify-email", desc: "Verify email using the token sent via email.", body: { token: "..." } },
  { group: "Auth", method: "POST", path: "/auth/forgot-password", desc: "Request a password reset link.", body: { email: "user@example.com" } },
  { group: "Auth", method: "POST", path: "/auth/reset-password", desc: "Reset password using a valid reset token.", body: { token: "...", new_password: "NewPass123" } },
  { group: "Passwordless", method: "POST", path: "/auth/magic-link/request", desc: "Send a magic login link via email.", body: { email: "user@example.com" } },
  { group: "Passwordless", method: "POST", path: "/auth/otp-login/request", desc: "Send an OTP code via SMS/WhatsApp.", body: { phone: "+6281234567890" } },
  { group: "Passwordless", method: "POST", path: "/auth/anonymous", desc: "Create an anonymous session.", body: {} },
  { group: "MFA", method: "POST", path: "/auth/mfa/totp/setup", desc: "Start TOTP enrollment, returns QR provisioning URI." },
  { group: "MFA", method: "POST", path: "/auth/mfa/totp/verify", desc: "Verify TOTP code during login.", body: { mfa_token: "...", code: "123456" } },
  { group: "MFA", method: "POST", path: "/auth/mfa/push/start", desc: "Trigger push approval on an active device." },
  { group: "Sessions", method: "GET", path: "/auth/sessions", desc: "List all active sessions/devices." },
  { group: "Sessions", method: "DELETE", path: "/auth/sessions/{id}", desc: "Revoke a specific device session." },
  { group: "Profile", method: "GET", path: "/profile", desc: "Get current user's profile." },
  { group: "Profile", method: "PATCH", path: "/profile", desc: "Update profile fields.", body: { name: "New Name" } },
  { group: "Profile", method: "POST", path: "/profile/change-password", desc: "Change password (requires verified email).", body: { old_password: "...", new_password: "..." } },
  { group: "Profile", method: "GET", path: "/profile/export", desc: "Export all user data (GDPR)." },
  { group: "Profile", method: "DELETE", path: "/profile", desc: "Permanently delete account (confirm=true)." },
  { group: "Admin", method: "GET", path: "/admin/users", desc: "List users for the current tenant (paginated)." },
  { group: "Admin", method: "GET", path: "/admin/metrics", desc: "Get DAU/MAU/conversion/login metrics." },
  { group: "Admin", method: "GET", path: "/admin/audit-logs", desc: "View audit trail for the tenant." },
];

const nav = document.getElementById("docNav");
const groups = [...new Set(ENDPOINTS.map((e) => e.group))];
nav.innerHTML = groups.map((g) => `
  <div class="doc-group">
    <div class="doc-group-title">${g}</div>
    ${ENDPOINTS.filter((e) => e.group === g).map((e, i) => `
      <a class="doc-link" data-path="${e.path}" data-method="${e.method}">
        <span class="method-tag ${e.method.toLowerCase()}">${e.method}</span> ${e.path}
      </a>
    `).join("")}
  </div>
`).join("");

document.querySelectorAll(".doc-link").forEach((link) => {
  link.addEventListener("click", () => {
    const path = link.dataset.path;
    const method = link.dataset.method;
    const ep = ENDPOINTS.find((e) => e.path === path && e.method === method);
    document.getElementById("endpointDetail").innerHTML = `
      <div class="endpoint-card">
        <div class="endpoint-title">
          <span class="method-tag ${ep.method.toLowerCase()}">${ep.method}</span>
          <code>${ep.path}</code>
        </div>
        <p>${ep.desc}</p>
        ${ep.body ? `<pre>${JSON.stringify(ep.body, null, 2)}</pre>` : ""}
        <pre>curl -X ${ep.method} ${window.location.origin}${ep.path} \\
  -H "X-API-Key: caca-pk_xxxx" \\
  -H "Content-Type: application/json"${ep.body ? ` \\\n  -d '${JSON.stringify(ep.body)}'` : ""}</pre>
      </div>
    `;
  });
});

document.getElementById("docSearch").addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll(".doc-link").forEach((link) => {
    link.style.display = link.dataset.path.toLowerCase().includes(q) ? "flex" : "none";
  });
});