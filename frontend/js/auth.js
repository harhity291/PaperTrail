/* Handles client-side behavior for the login and registration pages. */

/* Grab references to the login form, registration form, and shared status message element */
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const formMessage = document.getElementById("form-message");

/* Updates the feedback text and applies a styling class (defaults to "error") */
function showMessage(text, type = "error") {
  formMessage.textContent = text;
  formMessage.className = `message ${type}`;
}

/* Show / hide password interface */
document.querySelectorAll("[data-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    /* Look up the target input using the ID stored in the button's data-toggle attribute */
    const input = document.getElementById(button.dataset.toggle);
    input.type = input.type === "password" ? "text" : "password";
  });
});

/* Messages passed in the address bar, e.g. login.html?expired=1 */
const params = new URLSearchParams(window.location.search);
if (params.has("expired")) showMessage("Your session ended. Please sign in again.", "success");
if (params.has("offline")) showMessage("The server is not running. Start the backend and try again.");

/* Sends the form to the backend; on success, saves the token and opens the dashboard */
async function submitForm(form, path, body) {
  const button = form.querySelector("button[type=submit]");
  /* Prevent duplicate submissions while the request is in flight */
  button.disabled = true;
  try {
    const { res, data } = await postJson(path, body);
    /* Handle HTTP error responses returned by the backend */
    if (!res.ok) {
      showMessage(data.error || "Something went wrong.");
      return;
    }
    /* Persist session token and navigate to the main dashboard */
    setToken(data.token);
    window.location.href = "dashboard.html";
  } catch (err) {
    /* Network error or unreachable backend server */
    showMessage("Could not reach the server. Is the backend running?");
  } finally {
    /* Always re-enable the submit button once the request finishes */
    button.disabled = false;
  }
}

/* ---------- Login page (POST /auth/login) ---------- */
if (loginForm) {
  loginForm.addEventListener("submit", (e) => {
    /* Stop full-page reload so submission can be handled via fetch/JSON */
    e.preventDefault();
    const identifier = document.getElementById("identifier").value.trim();
    const password = document.getElementById("password").value;

    /* Basic client-side presence check before sending request */
    if (!identifier || !password) {
      showMessage("Please enter your email or phone and your password.");
      return;
    }
    submitForm(loginForm, "/auth/login", { identifier, password });
  });
}

/* ---------- Registration page (POST /auth/register) ---------- */
if (registerForm) {
  registerForm.addEventListener("submit", (e) => {
    /* Stop full-page reload so submission can be handled via fetch/JSON */
    e.preventDefault();
    const body = {
      first_name: document.getElementById("first-name").value.trim(),
      last_name: document.getElementById("last-name").value.trim(),
      email: document.getElementById("email").value.trim(),
      phone: document.getElementById("phone").value.trim(),
      password: document.getElementById("password").value,
    };

    /* Quick checks here; the backend checks everything again */
    if (!body.first_name || !body.last_name) return showMessage("Please enter your first and last name.");
    if (!body.email && !body.phone) return showMessage("Enter an email address or a phone number.");
    if (body.password.length < 8) return showMessage("Password must be at least 8 characters.");

    submitForm(registerForm, "/auth/register", body);
  });
}

/* If the user already has a valid session token, skip login/register and go to the dashboard */
redirectIfLoggedIn();
