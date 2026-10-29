// Shared code for every PaperTrail page.

const API_BASE = "http://localhost:5001";

// ---------- Login token (kept in the browser so a refresh keeps you logged in) ----------
function getToken() {
  try { return localStorage.getItem("pt-token"); } catch (e) { return null; }
}

function setToken(value) {
  try {
    if (value) localStorage.setItem("pt-token", value);
    else localStorage.removeItem("pt-token");
  } catch (e) { /* storage blocked */ }
}

// ---------- Calling the backend ----------
// Adds the token to every request, and sends you to the login page if it has expired.
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401 && token && !path.startsWith("/auth/login")) {
    setToken(null);
    window.location.href = "login.html?expired=1";
  }
  return res;
}

async function postJson(path, body) {
  const res = await api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { res, data: await res.json() };
}

// ---------- Page guards ----------
// On the dashboard: make sure someone is logged in, and return their details.
async function requireLogin() {
  if (!getToken()) {
    window.location.href = "login.html";
    return null;
  }
  try {
    const res = await api("/auth/me");
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    // Backend is not running: go to the login page, which shows a clear message
    window.location.href = "login.html?offline=1";
    return null;
  }
}

// On the login and register pages: skip them if you are already logged in.
async function redirectIfLoggedIn() {
  if (!getToken()) return;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${getToken()}` } });
    if (res.ok) window.location.href = "dashboard.html";
    else setToken(null);
  } catch (err) { /* backend offline: stay on the page */ }
}

// ---------- Helpers ----------
async function isBackendOnline() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch (err) {
    return false;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatSize(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
