// Dashboard page: upload PDFs, see your documents, ask questions about the selected one.

const $ = (id) => document.getElementById(id);

const dropzone = $("dropzone");
const fileInput = $("file-input");
const uploadMessage = $("upload-message");
const docList = $("doc-list");
const chatLog = $("chat-log");
const askForm = $("ask-form");
const questionInput = $("question");
const sendBtn = $("send-btn");
const askTarget = $("ask-target");

let jobs = [];                // the user's documents, from GET /jobs
let selectedDocId = null;     // the document questions are asked about
let pollTimer = null;
const histories = {};         // doc_id -> [{ role, content, sources }]

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
  await loadDocuments();
  if (!selectedDocId && jobs.length) selectDocument(jobs[0].doc_id);
  else renderChat();
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
    showUploadMessage(`${data.filename} uploaded. Reading it now…`, "success");
    selectedDocId = data.doc_id;
    await loadDocuments();
    renderChat();
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
  clearTimeout(pollTimer);
  try {
    const res = await api("/jobs");
    if (!res.ok) return;
    jobs = await res.json();
    renderDocuments();
    updateSummary();
    updateAskState();
    // While any document is still being read, check again shortly
    if (jobs.some((job) => job.status === "queued" || job.status === "processing")) {
      pollTimer = setTimeout(loadDocuments, 1500);
    }
  } catch (err) {
    // Server offline: keep what is shown
  }
}

function renderDocuments() {
  docList.innerHTML = "";
  if (jobs.length === 0) {
    docList.innerHTML = '<li class="empty">No documents yet.</li>';
    return;
  }
  jobs.forEach((job) => {
    const li = document.createElement("li");
    li.className = "doc-item" + (job.doc_id === selectedDocId ? " selected" : "");
    li.tabIndex = 0;
    li.setAttribute("role", "button");
    const time = new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const pages = job.pages ? ` · ${job.pages} ${job.pages === 1 ? "page" : "pages"}` : "";
    li.innerHTML = `
      <span class="doc-icon">PDF</span>
      <div class="doc-info">
        <strong>${escapeHtml(job.filename)}</strong>
        <small>${formatSize(job.size_bytes)}${pages} · uploaded at ${time}</small>
        ${job.status === "failed" ? `<small class="doc-error">${escapeHtml(job.error || "Could not read this PDF.")}</small>` : ""}
      </div>
      <span class="status ${job.status}">${job.status === "done" ? "ready" : job.status}</span>
      <button class="doc-delete" type="button" title="Delete document" aria-label="Delete ${escapeHtml(job.filename)}">×</button>
    `;
    li.addEventListener("click", () => selectDocument(job.doc_id));
    li.addEventListener("keydown", (e) => {
      if (e.target === li && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); selectDocument(job.doc_id); }
    });
    li.querySelector(".doc-delete").addEventListener("click", (e) => {
      e.stopPropagation();
      deleteDocument(job);
    });
    docList.appendChild(li);
  });
}

function updateSummary() {
  const total = jobs.reduce((sum, job) => sum + (job.size_bytes || 0), 0);
  $("sum-docs").textContent = jobs.length;
  $("sum-size").textContent = formatSize(total);
  $("sum-queued").textContent = jobs.filter((job) => job.status === "queued" || job.status === "processing").length;
}

async function deleteDocument(job) {
  if (!confirm(`Delete "${job.filename}" and its chat?`)) return;
  try {
    const res = await api(`/docs/${job.doc_id}`, { method: "DELETE" });
    if (!res.ok) return showUploadMessage("Could not delete that document.", "error");
  } catch (err) {
    return showUploadMessage("Could not reach the server.", "error");
  }
  delete histories[job.doc_id];
  if (selectedDocId === job.doc_id) selectedDocId = null;
  showUploadMessage(`${job.filename} deleted.`, "success");
  await loadDocuments();
  if (!selectedDocId && jobs.length) selectDocument(jobs[0].doc_id);
  else renderChat();
}

// ---------- Choosing which document to ask about ----------
function selectedJob() {
  return jobs.find((job) => job.doc_id === selectedDocId) || null;
}

function selectDocument(docId) {
  selectedDocId = docId;
  renderDocuments();
  renderChat();
  if (!questionInput.disabled) questionInput.focus();
}

// Updates the "Asking about…" line and enables or disables the question box
function updateAskState() {
  const job = selectedJob();
  const ready = job && job.status === "done";
  questionInput.disabled = sendBtn.disabled = !ready;

  if (!job) {
    askTarget.textContent = "No document selected";
    questionInput.placeholder = "Select a document first";
  } else if (job.status === "failed") {
    askTarget.textContent = job.filename;
    questionInput.placeholder = "This document could not be read";
  } else if (!ready) {
    askTarget.textContent = `${job.filename} · reading…`;
    questionInput.placeholder = "Reading the document…";
  } else {
    askTarget.textContent = `Asking about: ${job.filename}`;
    questionInput.placeholder = "e.g. What is the main conclusion?";
  }
}

function renderChat() {
  updateAskState();
  chatLog.innerHTML = "";
  const job = selectedJob();
  if (!job) {
    addBubble("Upload a PDF, then pick it from the list and ask me anything about it.", "bot");
    return;
  }
  const history = histories[job.doc_id] || [];
  if (history.length === 0) {
    addBubble(job.status === "failed"
      ? "I couldn't read this PDF. Scanned PDFs need OCR first."
      : "Ask a question about this document. I'll answer only from what it says.", "bot");
  }
  history.forEach((turn) => addBubble(turn.content, turn.role === "user" ? "user" : "bot", turn.sources));
}

// ---------- Ask a question (POST /ask) ----------
askForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  const job = selectedJob();
  if (!question || !job) return;

  const docId = job.doc_id;
  const history = histories[docId] = histories[docId] || [];
  const past = history.map(({ role, content }) => ({ role, content }));

  if (history.length === 0) chatLog.innerHTML = "";
  addBubble(question, "user");
  questionInput.value = "";
  questionInput.disabled = sendBtn.disabled = true;
  const pending = addBubble("Reading the document…", "bot pending");

  try {
    const { res, data } = await postJson("/ask", { doc_id: docId, question, history: past });
    pending.remove();
    if (!res.ok) {
      if (selectedDocId === docId) addBubble(data.error || "Something went wrong.", "bot error");
    } else {
      history.push({ role: "user", content: question }, { role: "assistant", content: data.answer, sources: data.sources });
      if (selectedDocId === docId) addBubble(data.answer, "bot", data.sources);
    }
  } catch (err) {
    pending.remove();
    addBubble("Could not reach the server. Is the backend running?", "bot error");
  }
  updateAskState();
  if (!questionInput.disabled) questionInput.focus();
});

function addBubble(text, who, sources) {
  const div = document.createElement("div");
  div.className = `bubble ${who}`;
  div.textContent = text;
  if (sources && sources.length) {
    const details = document.createElement("details");
    details.className = "sources";
    const pages = [...new Set(sources.map((s) => s.page))].join(", ");
    const summary = document.createElement("summary");
    summary.textContent = `Passages used (pages ${pages})`;
    details.appendChild(summary);
    sources.forEach((s) => {
      const p = document.createElement("div");
      const label = document.createElement("strong");
      label.textContent = `Page ${s.page}`;
      p.appendChild(label);
      p.appendChild(document.createTextNode(s.text));
      details.appendChild(p);
    });
    div.appendChild(details);
  }
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

start();
