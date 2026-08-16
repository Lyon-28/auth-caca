class CacaAuth {
  constructor({ baseUrl, publicKey }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.publicKey = publicKey;
    this.accessToken = null;
    this.refreshToken = null;
    this._loadFromStorage();
  }
  
  _loadFromStorage() {
    this.accessToken = localStorage.getItem("caca_access_token");
    this.refreshToken = localStorage.getItem("caca_refresh_token");
  }
  
  _saveTokens(data) {
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    localStorage.setItem("caca_access_token", data.access_token);
    localStorage.setItem("caca_refresh_token", data.refresh_token);
  }
  
  _clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem("caca_access_token");
    localStorage.removeItem("caca_refresh_token");
  }
  
  async _request(method, path, body, auth = false) {
    const headers = { "Content-Type": "application/json", "X-API-Key": this.publicKey };
    if (auth && this.accessToken) headers["Authorization"] = `Bearer ${this.accessToken}`;
    
    let res = await fetch(`${this.baseUrl}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
    
    if (res.status === 401 && auth && this.refreshToken) {
      const refreshed = await this._tryRefresh();
      if (refreshed) {
        headers["Authorization"] = `Bearer ${this.accessToken}`;
        res = await fetch(`${this.baseUrl}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
      }
    }
    
    const json = await res.json();
    if (!json.success) {
      const err = new Error(json.error?.message || "request failed");
      err.code = json.error?.code;
      err.status = res.status;
      throw err;
    }
    return json.data;
  }
  
  async _tryRefresh() {
    try {
      const res = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": this.publicKey },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });
      const json = await res.json();
      if (json.success) {
        this._saveTokens(json.data);
        return true;
      }
      this._clearTokens();
      return false;
    } catch {
      return false;
    }
  }
  
  async register(email, password) {
    const data = await this._request("POST", "/auth/register", { email, password });
    this._saveTokens(data);
    return data;
  }
  
  async login(email, password) {
    const data = await this._request("POST", "/auth/login", { email, password });
    if (data.mfa_required) return data;
    this._saveTokens(data);
    return data;
  }
  
  async verifyMfa(method, mfaToken, code) {
    const data = await this._request("POST", `/auth/mfa/${method}/verify`, { mfa_token: mfaToken, code });
    this._saveTokens(data);
    return data;
  }
  
  async logout() {
    if (this.refreshToken) {
      await this._request("POST", "/auth/logout", { refresh_token: this.refreshToken }).catch(() => {});
    }
    this._clearTokens();
  }
  
  async me() {
    return this._request("GET", "/profile", null, true);
  }
  
  async updateProfile(fields) {
    return this._request("PATCH", "/profile", fields, true);
  }
  
  async changePassword(oldPassword, newPassword) {
    return this._request("POST", "/profile/change-password", { old_password: oldPassword, new_password: newPassword }, true);
  }
  
  async forgotPassword(email) {
    return this._request("POST", "/auth/forgot-password", { email });
  }
  
  async resetPassword(token, newPassword) {
    return this._request("POST", "/auth/reset-password", { token, new_password: newPassword });
  }
  
  async sendMagicLink(email) {
    return this._request("POST", "/auth/magic-link/request", { email });
  }
  
  async verifyMagicLink(token) {
    const data = await this._request("POST", "/auth/magic-link/verify", { token });
    this._saveTokens(data);
    return data;
  }
  
  isAuthenticated() {
    return !!this.accessToken;
  }
  
  startOAuth(provider) {
    window.location.href = `${this.baseUrl}/auth/oauth/${provider}/start`;
  }
  
  handleOAuthCallback() {
    const params = new URLSearchParams(window.location.search);
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (access && refresh) {
      this._saveTokens({ access_token: access, refresh_token: refresh });
      return true;
    }
    return false;
  }
}

if (typeof module !== "undefined") module.exports = CacaAuth;