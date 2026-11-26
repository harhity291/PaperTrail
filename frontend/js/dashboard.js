/* Dashboard page: upload PDFs, see your documents, ask questions about the selected file. */

/* Shorthand helper for looking up elements by ID */
const $ = (id) => document.getElementById(id);

/* Cache frequently accessed DOM elements for upload, document list, and chat UI */
const dropzone = $("dropzone");
const fileInput = $("file-input");
const uploadMessage = $("upload-message");
const docList = $("doc-list");
const chatLog = $("chat-log");
const askForm = $("ask-form");
const questionInput = $("question");
const sendBtn = $("send-btn");
const askTarget = $("ask-target");

/* Client-side state for document jobs, active selection, polling timer, and per-document chat history */
let jobs = [];                  /* the user's documents, from GET /jobs */
let selectedDocId = null;       /* the document questions are asked about */
let pollTimer = null;           /* Timeout handle used while documents are queued or processing */
const histories = {};           /* Maps doc_id -> array of { role, content, sources } turns */

/* ---------- Start: only show the page to logged-in users ---------- */
async function start() {
  /* Enforce authentication before revealing dashboard UI */
  const user = await requireLogin();
  if (!user) return;

  $("app").hidden = false;
  /* Populate user profile details, greeting, and localized current date */
  $("full-name").textContent = `${user.first_name} ${user.last_name}`;
  $("contact").textContent = user.email || user.phone || "";
  $("avatar").textContent = user.first_name.charAt(0);
  $("greeting").textContent = `${greetingForNow()}, ${user.first_name}`;
  $("today").textContent = new Date().toLocaleDateString("en-IE", { weekday: "long", day: "numeric", month: "long" });

  /* Check backend health immediately and re-check every 10 seconds */
  updateServerPill();
  setInterval(updateServerPill, 10000);
  /* Load documents and select the first available document if none is chosen yet */
  await loadDocuments();
  if (!selectedDocId && jobs.length) selectDocument(jobs[0].doc_id);
  else renderChat();
}

/* Returns a time-appropriate greeting based on the current local hour */
function greetingForNow() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/* Updates the server status badge styling and label */
async function updateServerPill() {
  const online = await isBackendOnline();
  $("server-pill").className = `server-pill ${online ? "online" : "offline"}`;
  $("server-pill").querySelector(".label").textContent = online ? "Server online" : "Server offline";
}

/* ---------- Log out ---------- */
$("logout-btn").addEventListener("click", async () => {
  /* Notify backend if reachable, then clear local token and return to landing page */
  try { await api("/auth/logout", { method: "POST" }); } catch (e) { /* ignore */ }
  setToken(null);
  window.location.href = "index.html";
});

/* ---------- Upload (POST /upload) ---------- */
async function uploadFile(file) {
  if (!file) return;
  /* Enforce PDF file type on the client before sending */
  if (file.type !== "application/pdf") {
    showUploadMessage("Please choose a PDF file.", "error");
    return;
  }

  /* Package file in FormData for multipart upload */
  const formData = new FormData();
  formData.append("file", file); /* Field name must match request.files["file"] in Flask */

  showUploadMessage(`Uploading ${file.name}…`);
  try {
    const res = await api("/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      showUploadMessage(data.error || "Upload failed.", "error");
      return;
    }
    
    /* Select the newly uploaded document and refresh the job list */
    showUploadMessage(`${data.filename} uploaded. Reading it now…`, "success");
    selectedDocId = data.doc_id;
    await loadDocuments();
    renderChat();
  } catch (err) {
    showUploadMessage("Could not reach the server. Is the backend running?", "error");
  }
}

/* Displays upload or document action status messages */
function showUploadMessage(text, type = "") {
  uploadMessage.textContent = text;
  uploadMessage.className = `message ${type}`;
}

/* Handle file selection via the hidden file input, then reset input value so re-uploading works */
fileInput.addEventListener("change", () => {
  uploadFile(fileInput.files[0]);
  fileInput.value = "";
});

/* Drag-and-drop event handlers for the dropzone */
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();   /* Required to allow dropping files */
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  uploadFile(e.dataTransfer.files[0]);
});

/* ---------- My documents (GET /jobs) ---------- */
async function loadDocuments() {
  /* Cancel any pending poll before starting a fresh fetch */
  clearTimeout(pollTimer);
  try {
    const res = await api("/jobs");
    if (!res.ok) return;
    jobs = await res.json();
    renderDocuments();
    updateSummary();
    updateAskState();
    /* While any document is still being read, check again shortly */
    if (jobs.some((job) => job.status === "queued" || job.status === "processing")) {
      pollTimer = setTimeout(loadDocuments, 1500);
    }
  } catch (err) {
      /* Keep existing UI state if server is temporarily unreachable */
  }
}

/* Renders the list of uploaded documents and attaches selection/keyboard/delete handlers */
function renderDocuments() {
  docList.innerHTML = "";
  if (jobs.length === 0) {
    docList.innerHTML = '<li class="empty">No documents yet.</li>';
    return;
  }
  jobs.forEach((job) => {
    const li = document.createElement("li");
    li.className = "doc-item" + (job.doc_id === selectedDocId ? " selected" : "");
    li.tabIndex = 0;  /* Makes list item focusable via keyboard */
    li.setAttribute("role", "button");
    const time = new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const pages = job.pages ? ` · ${job.pages} ${job.pages === 1 ? "page" : "pages"}` : "";
    /* Escape dynamic strings with escapeHtml to prevent XSS */
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
    /* Select document on click */
    li.addEventListener("click", () => selectDocument(job.doc_id));
    /* Allow selecting with Enter or Space when focused directly on the item */
    li.addEventListener("keydown", (e) => {
      if (e.target === li && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); selectDocument(job.doc_id); }
    });
    /* Prevent delete click from bubbling up and selecting the document */
    li.querySelector(".doc-delete").addEventListener("click", (e) => {
      e.stopPropagation();
      deleteDocument(job);
    });
    docList.appendChild(li);
  });
}

/* Updates top summary cards (total documents, total size, and active processing count) */
function updateSummary() {
  const total = jobs.reduce((sum, job) => sum + (job.size_bytes || 0), 0);
  $("sum-docs").textContent = jobs.length;
  $("sum-size").textContent = formatSize(total);
  $("sum-queued").textContent = jobs.filter((job) => job.status === "queued" || job.status === "processing").length;
}

/* Deletes a document on the backend and removes its local chat history */
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
  /* Select another document if available, otherwise reset chat view */
  if (!selectedDocId && jobs.length) selectDocument(jobs[0].doc_id);
  else renderChat();
}

/* ---------- Choosing which document to ask about ---------- */

/* Returns the job object matching selectedDocId, or null */
function selectedJob() {
  return jobs.find((job) => job.doc_id === selectedDocId) || null;
}

/* Sets the active document, refreshes UI, and focuses the question input if ready */
function selectDocument(docId) {
  selectedDocId = docId;
  renderDocuments();
  renderChat();
  if (!questionInput.disabled) questionInput.focus();
}

/* Updates the "Asking about…" line and enables or disables the question box */
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

/* Renders chat bubbles for the currently selected document */
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

/* ---------- Ask a question (POST /ask) ---------- */
askForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  const job = selectedJob();
  if (!question || !job) return;

  const docId = job.doc_id;
  const history = histories[docId] = histories[docId] || [];
  /* Send prior conversation turns without source metadata to the backend */
  const past = history.map(({ role, content }) => ({ role, content }));

  if (history.length === 0) chatLog.innerHTML = "";
  addBubble(question, "user");
  
  /* Lock input while waiting for the response and show a temporary pending bubble */
  questionInput.value = "";
  questionInput.disabled = sendBtn.disabled = true;
  const pending = addBubble("Reading the document…", "bot pending");

  try {
    const { res, data } = await postJson("/ask", { doc_id: docId, question, history: past });
    pending.remove();
    if (!res.ok) {
      /* Only append to visible log if the user hasn't switched documents meanwhile */
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

/* Appends a message bubble (and optional collapsible source passages) to the chat log */
function addBubble(text, who, sources) {
  const div = document.createElement("div");
  div.className = `bubble ${who}`;
  div.textContent = text;
  /* Render expandable source citations if returned with the answer */
  if (sources && sources.length) {
    const details = document.createElement("details");
    details.className = "sources";
    /* Deduplicate page numbers for the summary header */
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
  /* Auto-scroll to the newest message */
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

/* Initialize the dashboard on script load */
start();
