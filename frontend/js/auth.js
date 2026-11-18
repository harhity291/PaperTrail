// Log in / Create account popup on the home page (index.html).

const authModal = document.getElementById("auth-modal");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

// Each form has its own message line (the <p class="message"> inside it)
function showMessage(form, text, type = "error") {
  const message = form.querySelector(".message");
  message.textContent = text;
  message.className = `message ${type}`;
}

function clearMessages() {
  document.querySelectorAll(".auth-form .message").forEach((m) => {
    m.textContent = "";
    m.className = "message";
  });
}

// ---------- Tabs: "Log in" and "Create account" ----------
function showTab(name) {
  document.querySelectorAll(".auth-tab").forEach((tab) => {
    tab.setAttribute("aria-selected", tab.dataset.tab === name ? "true" : "false");
  });
  document.getElementById("panel-login").hidden = name !== "login";
  document.getElementById("panel-register").hidden = name !== "register";
  clearMessages();
  const firstInput = document.querySelector(`#panel-${name} input`);
  if (firstInput) firstInput.focus();
}

// ---------- Opening and closing the popup ----------
function openAuth(tab = "login") {
  authModal.hidden = false;
  document.body.classList.add("modal-open");
  showTab(tab);
}

function closeAuth() {
  authModal.hidden = true;
  document.body.classList.remove("modal-open");
}

// Buttons like "Log in" and "Get started" open the popup on the right tab
document.querySelectorAll("[data-open-auth]").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    openAuth(link.dataset.openAuth);
  });
});

// Tab buttons, and the "Create one" / "Log in instead" links at the bottom
document.querySelectorAll("[data-tab]").forEach((tab) => {
  tab.addEventListener("click", () => showTab(tab.dataset.tab));
});
document.querySelectorAll("[data-switch-tab]").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    showTab(link.dataset.switchTab);
  });
});

// Close with the ✕ button, by clicking outside the card, or with Esc
document.getElementById("auth-close").addEventListener("click", closeAuth);
authModal.addEventListener("click", (e) => { if (e.target === authModal) closeAuth(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !authModal.hidden) closeAuth(); });

// Show / hide password
document.querySelectorAll("[data-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.toggle);
    input.type = input.type === "password" ? "text" : "password";
  });
});

// ---------- Opening the popup from the address bar ----------
// index.html?login=1   -> Log in tab   (also used when a session expires)
// index.html?signup=1  -> Create account tab
const params = new URLSearchParams(window.location.search);
if (params.has("signup")) openAuth("register");
else if (params.has("login")) openAuth("login");
if (params.has("expired")) showMessage(loginForm, "Your session ended. Please sign in again.", "success");
if (params.has("offline")) showMessage(loginForm, "The server is not running. Start the backend and try again.");

// Sends the form to the backend; on success, saves the token and opens the dashboard
async function submitForm(form, path, body) {
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const { res, data } = await postJson(path, body);
    if (!res.ok) {
      showMessage(form, data.error || "Something went wrong.");
      return;
    }
    setToken(data.token);
    window.location.href = "dashboard.html";
  } catch (err) {
    showMessage(form, "Could not reach the server. Is the backend running?");
  } finally {
    button.disabled = false;
  }
}

// ---------- Log in (POST /auth/login) ----------
loginForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const identifier = document.getElementById("identifier").value.trim();
  const password = document.getElementById("login-password").value;

  if (!identifier || !password) {
    showMessage(loginForm, "Please enter your email or phone and your password.");
    return;
  }
  submitForm(loginForm, "/auth/login", { identifier, password });
});

// ---------- Create account (POST /auth/register) ----------
registerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const body = {
    first_name: document.getElementById("first-name").value.trim(),
    last_name: document.getElementById("last-name").value.trim(),
    email: document.getElementById("email").value.trim(),
    phone: document.getElementById("phone").value.trim(),
    password: document.getElementById("register-password").value,
  };

  // Quick checks here; the backend checks everything again
  if (!body.first_name || !body.last_name) return showMessage(registerForm, "Please enter your first and last name.");
  if (!body.email && !body.phone) return showMessage(registerForm, "Enter an email address or a phone number.");
  if (body.password.length < 8) return showMessage(registerForm, "Password must be at least 8 characters.");

  submitForm(registerForm, "/auth/register", body);
});
