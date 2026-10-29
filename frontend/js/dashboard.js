// Dashboard page: upload PDFs, see your documents, ask questions.

const $ = (id) => document.getElementById(id);

const dropzone = $("dropzone");
const fileInput = $("file-input");
const uploadMessage = $("upload-message");
const docList = $("doc-list");
const chatLog = $("chat-log");
const askForm = $("ask-form");
const questionInput = $("question");

// ---------- Start: only show the page to logged-in users ----------
async function start() {
  const user = await requireLogin();
  if (!user) return;

  $("app").hidden = false;
  $("full-name").textContent = `${user.first_name} ${user.last_name}`;
  $("contact").textContent = user.email || user.phone || "";
  $("avatar").textContent = user.first_name.charAt(0);
  $("greeting").textContent = `${greetingForNow()}, ${user.first_name}`;
  $("today").textContent = new Date().toLocaleDateString("en-IE", { weekday: "long", day: "numeric", month: "long" });

  updateServerPill();
  setInterval(updateServerPill, 10000);
  loadDocuments();
}

function greetingForNow() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

async function updateServerPill() {
  const online = await isBackendOnline();
  $("server-pill").className = `server-pill ${online ? "online" : "offline"}`;
  $("server-pill").querySelector(".label").textContent = online ? "Server online" : "Server offline";
}

// ---------- Log out ----------
$("logout-btn").addEventListener("click", async () => {
  try { await api("/auth/logout", { method: "POST" }); } catch (e) { /* ignore */ }
  setToken(null);
  window.location.href = "index.html";
});

// ---------- Upload (POST /upload) ----------
async function uploadFile(file) {
  if (!file) return;
  if (file.type !== "application/pdf") {
    showUploadMessage("Please choose a PDF file.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file); // must match request.files["file"] in Flask

  showUploadMessage(`Uploading ${file.name}…`);
  try {
    const res = await api("/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      showUploadMessage(data.error || "Upload failed.", "error");
      return;
    }
    showUploadMessage(`${data.filename} uploaded.`, "success");
    loadDocuments();
  } catch (err) {
    showUploadMessage("Could not reach the server. Is the backend running?", "error");
  }
}

function showUploadMessage(text, type = "") {
  uploadMessage.textContent = text;
  uploadMessage.className = `message ${type}`;
}

fileInput.addEventListener("change", () => {
  uploadFile(fileInput.files[0]);
  fileInput.value = "";
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  uploadFile(e.dataTransfer.files[0]);
});

// ---------- My documents (GET /jobs) ----------
async function loadDocuments() {
  try {
    const res = await api("/jobs");
    if (!res.ok) return;
    const jobs = await res.json();
    renderDocuments(jobs);
    updateSummary(jobs);
  } catch (err) {
    // Server offline: keep what is shown
  }
}

function renderDocuments(jobs) {
  docList.innerHTML = "";
  if (jobs.length === 0) {
    docList.innerHTML = '<li class="empty">No documents yet.</li>';
    return;
  }
  jobs.forEach((job) => {
    const li = document.createElement("li");
    const time = new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    li.innerHTML = `
      <span class="doc-icon">PDF</span>
      <div class="doc-info">
        <strong>${escapeHtml(job.filename)}</strong>
        <small>${formatSize(job.size_bytes)} · uploaded at ${time}</small>
      </div>
      <span class="status">${job.status}</span>
    `;
    docList.appendChild(li);
  });
}

function updateSummary(jobs) {
  const total = jobs.reduce((sum, job) => sum + (job.size_bytes || 0), 0);
  $("sum-docs").textContent = jobs.length;
  $("sum-size").textContent = formatSize(total);
  $("sum-queued").textContent = jobs.filter((job) => job.status === "queued").length;
}

// ---------- Ask a question (POST /ask) ----------
askForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  addBubble(question, "user");
  questionInput.value = "";

  try {
    const { data } = await postJson("/ask", { question });
    addBubble(data.answer || data.message || data.error, "bot");
  } catch (err) {
    addBubble("Could not reach the server.", "bot");
  }
});

function addBubble(text, who) {
  const div = document.createElement("div");
  div.className = `bubble ${who}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

start();
