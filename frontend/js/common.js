/* Shared utilities, API wrapper, and auth guards code for every PaperTrail page. */

/* Base URL of the local backend server */
const API_BASE = "http://localhost:5001";

// ---------- Login token (kept in the browser so a refresh keeps you logged in) ----------
/* Retrieves the stored authentication token, returning null if unavailable or blocked */
function getToken() {
  try { return localStorage.getItem("pt-token"); } catch (e) { return null; }
}

/* Saves a new token to localStorage, or removes it when value is falsy (e.g., on logout/expiry) */
function setToken(value) {
  try {
    if (value) localStorage.setItem("pt-token", value);
    else localStorage.removeItem("pt-token");
  } catch (e) { /* Storage access may fail in private browsing or restricted contexts */ }
}

/* ---------- Calling the backend ---------- */
/* Adds the token to every request, and sends you to the login page if it has expired. */
async function api(path, options = {}) {
  /* Preserve any custom headers passed by the caller */
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  /* Attach Bearer token if the user is currently signed in */
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  /* Clear stale token and redirect to login if an authenticated request returns 401 Unauthorized */
  if (res.status === 401 && token && !path.startsWith("/auth/login")) {
    setToken(null);
    window.location.href = "login.html?expired=1";
  }
  return res;
}

/* Helper for sending JSON payloads via POST and parsing both response and JSON body */
async function postJson(path, body) {
  const res = await api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { res, data: await res.json() };
}

/* ---------- Page route guards ---------- */
/* Protects private pages (such as the dashboard): redirects to login if unauthenticated or offline */
async function requireLogin() {
  if (!getToken()) {
    window.location.href = "login.html";
    return null;
  }
  try {
    /* Verify token validity and fetch the current user's profile */
    const res = await api("/auth/me");
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    /* Backend is not running: go to the login page, which shows a clear message with offline notice */
    window.location.href = "login.html?offline=1";
    return null;
  }
}

/* On the login and register pages: skip them if you are already logged in. */
async function redirectIfLoggedIn() {
  if (!getToken()) return;
  try {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${getToken()}` } });
    if (res.ok) window.location.href = "dashboard.html";
     /* Token is invalid or rejected; clear it so the user can sign in cleanly */
    else setToken(null);
  } catch (err) { /* backend offline: stay on the auth page instead of redirecting */ }
}

/* ----------General Helpers ---------- */
/* Pings the /health endpoint to check whether the backend API is reachable */
async function isBackendOnline() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch (err) {
    return false;
  }
}

/* Escapes special HTML characters via textContent so untrusted text is safe to inject as HTML */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/* Formats a byte count into a human-readable string (B, KB, or MB) */
function formatSize(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
