const API_BASE = window.location.origin;
let apiKey = localStorage.getItem("caca_admin_key") || "";
document.getElementById("apiKeyInput").value = apiKey;
document.getElementById("apiKeyInput").addEventListener("change", (e) => {
  apiKey = e.target.value.trim();
  localStorage.setItem("caca_admin_key", apiKey);
  loadOverview();
});

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: { "X-API-Key": apiKey } });
  const json = await res.json();
  if (!json.success) throw new Error(json.error.message);
  return json;
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "X-API-Key": apiKey, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json();
  if (!json.success) throw new Error(json.error.message);
  return json;
}

async function apiPatch(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "X-API-Key": apiKey, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    const view = btn.dataset.view;
    document.getElementById(`view-${view}`).classList.add("active");
    document.getElementById("viewTitle").textContent = btn.textContent.trim();
    if (view === "overview") loadOverview();
    if (view === "users") loadUsers();
    if (view === "logs") loadLogs();
    if (view === "webhooks") loadWebhooks();
  });
});

async function loadOverview() {
  if (!apiKey) return;
  try {
    const { data } = await apiGet("/admin/metrics");
    const container = document.getElementById("metricCards");
    const cards = [
      ["DAU", data.dau],
      ["MAU", data.mau],
      ["Total Users", data.total_users],
      ["Signups (30d)", data.signups_30d],
      ["Login Success Rate", data.login_success_rate !== null ? `${(data.login_success_rate * 100).toFixed(1)}%` : "-"],
      ["Avg Session (s)", data.avg_session_duration_seconds ?? "-"],
    ];
    container.innerHTML = cards.map(([label, value]) => `
      <div class="card"><div class="label">${label}</div><div class="value">${value}</div></div>
    `).join("");
  } catch (e) { console.error(e); }
}

async function loadUsers() {
  if (!apiKey) return;
  const { data } = await apiGet("/admin/users?limit=50");
  document.getElementById("usersBody").innerHTML = data.users.map((u) => `
    <tr>
      <td>${u.email}</td>
      <td><span class="badge ${u.status}">${u.status}</span></td>
      <td>${u.email_verified ? "✓" : "—"}</td>
      <td>${u.mfa_enabled ? "✓" : "—"}</td>
      <td>${new Date(u.created_at).toLocaleDateString()}</td>
      <td><button onclick="banUser('${u.id}')" class="btn-icon"><i class="fa-solid fa-ban"></i></button></td>
    </tr>
  `).join("");
}

async function banUser(id) {
  if (!confirm("Suspend this user?")) return;
  await apiPatch(`/admin/users/${id}/status`, { status: "suspended" });
  loadUsers();
}

async function loadLogs() {
  if (!apiKey) return;
  const { data } = await apiGet("/admin/audit-logs?limit=50");
  document.getElementById("logsBody").innerHTML = data.logs.map((l) => `
    <tr><td>${l.action}</td><td>${l.user_id ?? "-"}</td><td>${l.ip ?? "-"}</td><td>${new Date(l.created_at).toLocaleString()}</td></tr>
  `).join("");
}

async function loadWebhooks() {
  if (!apiKey) return;
  const { data } = await apiGet("/admin/webhooks");
  document.getElementById("webhooksBody").innerHTML = data.webhooks.map((w) => `
    <tr><td>${w.url}</td><td>${w.events.join(", ")}</td><td>${w.active ? "✓" : "—"}</td>
    <td><button onclick="deleteWebhook('${w.id}')" class="btn-icon"><i class="fa-solid fa-trash"></i></button></td></tr>
  `).join("");
}

document.getElementById("addWebhookBtn").addEventListener("click", async () => {
  const url = document.getElementById("webhookUrl").value.trim();
  const events = document.getElementById("webhookEvents").value.split(",").map((s) => s.trim()).filter(Boolean);
  if (!url || !events.length) return;
  await apiPost("/admin/webhooks", { url, events });
  loadWebhooks();
});

async function deleteWebhook(id) {
  await fetch(`${API_BASE}/admin/webhooks/${id}`, { method: "DELETE", headers: { "X-API-Key": apiKey } });
  loadWebhooks();
}

document.getElementById("refreshBtn").addEventListener("click", () => {
  const active = document.querySelector(".nav-item.active").dataset.view;
  if (active === "overview") loadOverview();
  if (active === "users") loadUsers();
  if (active === "logs") loadLogs();
  if (active === "webhooks") loadWebhooks();
});

if (apiKey) loadOverview();