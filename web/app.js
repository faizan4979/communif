const API_BASE_URL = "https://ddss-project-etdk.vercel.app";
const state = { token: localStorage.getItem("ddss_token"), user: JSON.parse(localStorage.getItem("ddss_user") || "null"), screen: "portal" };
const app = document.getElementById("app");
const sidebar = document.getElementById("sidebar");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
}
function notify(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.getElementById("toast-region").appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}
function saveSession(data) {
  state.token = data.token; state.user = data;
  localStorage.setItem("ddss_token", data.token); localStorage.setItem("ddss_user", JSON.stringify(data));
}
function clearSession() {
  state.token = null; state.user = null; localStorage.removeItem("ddss_token"); localStorage.removeItem("ddss_user");
}
function headers(json = false) {
  const result = {};
  if (json) result["Content-Type"] = "application/json";
  if (state.token) result["X-Auth-Token"] = state.token;
  return result;
}
class ApiError extends Error {
  constructor(message, status = 0, kind = "http") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}
async function api(path, options = {}) {
  const isMultipart = typeof FormData !== "undefined" && options.body instanceof FormData;
  const request = { ...options, headers: { ...headers(options.body !== undefined && !isMultipart), ...(options.headers || {}) } };
  let response;
  try { response = await fetch(`${API_BASE_URL}${path}`, request); }
  catch (error) {
    throw new ApiError(
      "Cannot connect to the DDSS backend. Check your connection or the browser's CORS error.",
      0,
      "network"
    );
  }
  if (!response.ok) {
    let detail = response.statusText;
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* non-JSON error */ }
    if (Array.isArray(payload?.detail)) {
      detail = payload.detail.map((item) => item.msg || item.message || "Invalid field").join("; ");
    } else {
      detail = payload?.detail || payload?.message || detail;
    }
    if (response.status === 401) { clearSession(); render(); }
    throw new ApiError(detail, response.status, "http");
  }
  return response;
}
async function json(path, options) {
  const response = await api(path, options);
  try { return await response.json(); }
  catch (_) { throw new ApiError("The backend returned a non-JSON response.", response.status, "response"); }
}
function apiErrorMessage(error) {
  if (!(error instanceof ApiError)) return error.message || "Unexpected error.";
  if (error.kind === "network") return error.message;
  const labels = {
    400: "Validation failed",
    401: "Authentication required",
    403: "You are not authorized for this action",
    404: "The requested form or endpoint was not found",
    409: "Duplicate registration",
    413: "The uploaded file is too large",
    422: "The submitted form is incomplete or malformed",
    500: "The backend encountered a server error",
    503: "Submission could not be saved because persistent file storage is temporarily unavailable. Please try again later."
  };
  if (error.status === 503) return labels[503];
  return `${labels[error.status] || `Request failed (${error.status})`}: ${error.message}`;
}
function formData(values) { const data = new FormData(); Object.entries(values).forEach(([key, value]) => data.append(key, value)); return data; }
function displayDateTime(value, fallback) {
  if (!value) return fallback;
  const parsed = new Date(String(value).replace(" ", "T"));
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}
function table(rows, columns) {
  if (!rows || !rows.length) return '<div class="notice">No records found.</div>';
  return `<div class="table-wrap"><table><thead><tr>${columns.map((c) => `<th>${esc(c.label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((c) => `<td>${esc(typeof c.value === "function" ? c.value(row) : row[c.key])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function metricGrid(stats) {
  const items = [["total_members", "Society Members"], ["total_volunteers", "Volunteers"], ["total_attendees", "Attendees"], ["total_events", "Events"], ["forms_open", "Open Forms"], ["registrations_pending", "Pending"], ["registrations_approved", "Approved"], ["attendance_present", "Present Attendance"]];
  return `<div class="grid">${items.map(([key, label]) => `<div class="metric"><span>${label}</span><strong>${esc(stats[key] || 0)}</strong></div>`).join("")}</div>`;
}
function renderSidebar() {
  const user = state.user;
  sidebar.innerHTML = `<div class="sidebar-branding"><img class="sidebar-logo" src="assets/duet_logo.png" alt="DUET"><div class="sidebar-brand-name">DDSS<br><span>DUET</span></div><img class="sidebar-logo" src="assets/ddss_logo.png" alt="DDSS"></div><p class="sidebar-tagline">"Inspire - Analyze - Innovate"</p>${user ? `<div class="sidebar-session"><span>LOGGED IN AS</span><strong>${esc(user.full_name)}</strong><b>${user.role === "admin" ? "👑 Administrator" : `🎖️ Cabinet: ${esc(user.title || "Member")}`}</b><small>@${esc(user.username)}</small></div>` : `<div class="public-mode">👤 Public Portal Mode<br><span>Students can browse and submit open forms.</span></div>`}
    <nav><button class="nav-button ${state.screen === "portal" ? "active" : ""}" data-screen="portal">📋 Student Registration</button>
    ${user ? `<button class="nav-button ${state.screen === "dashboard" ? "active" : ""}" data-screen="dashboard">📊 Admin Dashboard</button><button class="nav-button" id="logout">🚪 Sign Out</button>` : `<button class="nav-button ${state.screen === "login" ? "active" : ""}" data-screen="login">🔐 Cabinet & Admin Login</button>`}</nav>`;
  sidebar.querySelectorAll("[data-screen]").forEach((button) => button.addEventListener("click", () => { state.screen = button.dataset.screen; render(); }));
  document.getElementById("logout")?.addEventListener("click", async () => { try { if (state.token) await api("/api/auth/logout", { method: "POST" }); } catch (_) { /* local session still clears */ } clearSession(); state.screen = "portal"; render(); notify("Signed out."); });
}
function render() { renderSidebar(); if (state.screen === "login") renderLogin(); else if (state.screen === "dashboard" && state.user) renderDashboard(); else renderPortal(); }
function renderLogin() {
  app.innerHTML = `<div class="tabs"><button class="tab" data-screen="portal">📋 Student Registration Portal</button><button class="tab active">🔐 Cabinet & Admin Login</button></div><section class="panel login-panel"><h3>🔐 Dawood Data Science Society - Portal Sign In</h3><p class="caption">Authorized access for Society Admin and Cabinet Executive Members.</p><form id="login-form"><div class="form-grid"><label>Username<input name="username" placeholder="Enter your username" autocomplete="username" required></label><label>Password<input name="password" type="password" placeholder="Enter your password" autocomplete="current-password" required></label></div><div class="actions"><button class="button" type="submit">Sign In to Portal</button></div></form></section>`;
  document.querySelector(".tabs [data-screen=portal]").addEventListener("click", () => { state.screen = "portal"; render(); });
  document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const data = new FormData(event.target);
    try { const result = await json("/api/auth/login", { method: "POST", body: JSON.stringify({ username: data.get("username").trim().toLowerCase(), password: data.get("password") }) }); saveSession(result); state.screen = "dashboard"; render(); notify(`Welcome back, ${result.full_name}!`); }
    catch (error) { notify(error.message, "error"); }
  });
}
async function renderPortal() {
  app.innerHTML = '<div class="loading">Loading open registration forms…</div>';
  try {
    const forms = await json("/api/public/forms", { cache: "no-store" });
    if (!forms.length) { app.innerHTML = '<section class="panel"><h2>📋 Student Registration Portal</h2><div class="notice">No registration forms have been created yet. Please check back later.</div></section>'; return; }
    app.innerHTML = `<div class="tabs"><button class="tab active">📋 Student Registration Portal</button><button class="tab" data-screen="login">🔐 Cabinet & Admin Login</button></div><section class="hero"><h2>📋 Student Event & Volunteer Registration Portal</h2><p>Welcome to the <strong>Dawood Data Science Society</strong> official registration system. Only enrolled DUET students with valid roll numbers may submit.</p><p style="font-size:12px;color:#64748B;margin-top:8px;">Made by @ Hassan Ikram [25F-DS-052], Muhammad Faizan Ali [25F-DS-076], Faizan Ahmed [25F-DS-085], Muhammad Mudabbir Baig [25F-DS-087], Alishan Khan [25F-DS-093]</p></section>
      <section class="panel"><label>📌 Select an Event Registration Form<select id="public-form">${forms.map((f, i) => `<option value="${i}">${esc(f.form_id)} - ${esc(f.event_title)} (${esc(f.form_type)} Form)</option>`).join("")}</select></label><div id="public-form-content"></div></section>`;
    document.querySelector(".tabs [data-screen=login]").addEventListener("click", () => { state.screen = "login"; render(); });
    const select = document.getElementById("public-form");
    const show = () => renderPublicForm(forms[Number(select.value)]);
    select.addEventListener("change", show); show();
  } catch (error) { app.innerHTML = `<section class="panel"><div class="notice error">${esc(error.message)}</div></section>`; }
}
function renderPublicForm(form) {
  const open = form.computed_is_open;
  document.getElementById("public-form-content").innerHTML = `<div class="split" style="margin-top:16px"><div><h3>🎯 ${esc(form.event_title)}</h3><p><strong>Form Type:</strong> ${esc(form.form_type)}</p><p>${esc(form.description)}</p><p class="caption">Schedule: ${esc(displayDateTime(form.open_time, "Immediately"))} to ${esc(displayDateTime(form.close_time, "No deadline"))}</p></div><div><span class="status ${open ? "open" : "closed"}">${open ? "🟢 OPEN FOR REGISTRATION" : `🔴 CLOSED · ${esc(form.status_message)}`}</span></div></div>
    ${open ? `<hr><h3>📝 Submit Application</h3><form id="student-form"><div class="form-grid"><label>Candidate Full Name *<input name="candidate_name" minlength="3" maxlength="60" required></label><label>Roll Number *<input name="roll_no" placeholder="25F-DS-052" required></label><label>Pakistani Phone Number *<input name="phone_no" placeholder="03001234567" required></label><label>Department *<select name="department"><option>Data Science</option><option>Computer Science</option><option>Software Engineering</option><option>Artificial Intelligence</option><option>Cyber Security</option><option>Telecommunication</option></select></label><label style="grid-column:1/-1">University Email *<input name="university_email" type="email" placeholder="25f-ds-076@students.duet.edu.pk" required></label></div><label style="margin-top:13px">Mandatory Student ID Card Image *<input name="id_card_picture" type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" required></label><p class="caption">JPG, JPEG, or PNG only · maximum 80 KB.</p><div class="actions"><button class="button" type="submit">🚀 Submit Application</button></div></form>` : `<div class="notice warning">⚠️ This form is currently closed. Reason: ${esc(form.status_message)}. Submissions are disabled.</div>`}`;
  document.getElementById("student-form")?.addEventListener("submit", async (event) => {
    event.preventDefault(); const data = new FormData(event.target); const file = data.get("id_card_picture");
    const name = data.get("candidate_name").trim(); const fileType = (file.type || "").toLowerCase();
    if (name.length < 3 || name.length > 60) return notify("Candidate name must be between 3 and 60 characters.", "error");
    if (file.size > 81920) return notify("Image must be 80 KB or smaller.", "error");
    if (!["image/jpeg", "image/png"].includes(fileType)) return notify("Only JPG, JPEG, or PNG images are allowed.", "error");
    const rollNo = data.get("roll_no").trim().toUpperCase();
    const univEmail = data.get("university_email").trim().toLowerCase();
    if (!/^\d{2}[a-z]-[a-z]{2,5}-\d{2,4}@students\.duet\.edu\.pk$/i.test(univEmail)) return notify("Invalid university email. Use format like 25f-ds-076@students.duet.edu.pk", "error");
    const emailRollPart = univEmail.split("@")[0].toUpperCase();
    if (emailRollPart !== rollNo) return notify(`The roll number in university email (${emailRollPart}) does not match entered roll number (${rollNo}).`, "error");
    data.set("form_id", form.form_id); data.set("candidate_name", name); data.set("roll_no", rollNo); data.set("phone_no", data.get("phone_no").trim()); data.set("email", univEmail); data.set("university_email", univEmail);
    const button = event.target.querySelector("button"); button.disabled = true; button.textContent = "Submitting…";
    try { const result = await json("/api/public/submit", { method: "POST", body: data }); document.getElementById("student-form").innerHTML = `<div class="notice success"><h3>✅ Registration Confirmed</h3><p><strong>Reference Number:</strong> ${esc(result.reference_number)}</p><p><strong>Event:</strong> ${esc(result.event_title)} · <strong>Candidate:</strong> ${esc(result.candidate_name)}</p><p>Please save this reference number. Your submission entered the FIFO cabinet review queue.</p></div>`; notify("Application submitted successfully."); }
    catch (error) { button.disabled = false; button.textContent = "🚀 Submit Application"; notify(apiErrorMessage(error), "error"); }
  });
}
async function renderDashboard() {
  app.innerHTML = '<div class="loading">Loading dashboard…</div>';
  if (state.user.role === "admin") renderAdmin(); else renderCabinet();
}
async function loadStats() { return json("/api/dashboard/stats", { headers: headers() }); }
function dashboardShell(title, subtitle, tabs) {
  app.innerHTML = `<section class="hero"><h2>${title}</h2><p class="muted">${subtitle}</p></section><div id="dashboard-stats"></div><div class="panel"><div class="actions tab-actions">${tabs.map((tab) => `<button class="button secondary tab-button" data-tab="${tab.id}">${tab.label}</button>`).join("")}</div><div id="dashboard-panel"></div></div>`;
  document.querySelectorAll(".tab-button").forEach((button) => button.addEventListener("click", () => window.dashboardTabs[button.dataset.tab]()));
}
async function renderAdmin() {
  dashboardShell("👑 Admin Control Center", `Full system authority · Logged in as ${state.user.full_name}`, [{ id: "overview", label: "📊 Overview" }, { id: "forms", label: "📝 Forms" }, { id: "data", label: "🗄️ Data & DSA" }, { id: "cabinet", label: "👥 Cabinet" }, { id: "allowed", label: "📜 Allowed Rolls" }, { id: "audit", label: "💾 Audit & Downloads" }]);
  window.dashboardTabs = { overview: adminOverview, forms: adminForms, data: adminData, cabinet: adminCabinet, allowed: adminAllowed, audit: adminAudit };
  try { document.getElementById("dashboard-stats").innerHTML = metricGrid(await loadStats()); adminOverview(); } catch (error) { document.getElementById("dashboard-stats").innerHTML = `<div class="notice error">${esc(error.message)}</div>`; }
}
async function adminOverview() { const stats = await loadStats(); document.getElementById("dashboard-panel").innerHTML = `<h3>📊 Society Operations Overview</h3><div class="split" style="margin-top:16px"><div class="panel"><h4>Registration Status</h4>${["registrations_approved", "registrations_pending", "registrations_rejected"].map((k) => `<p>${k.replace("registrations_", "")}: <strong>${stats[k] || 0}</strong></p>`).join("")}</div><div class="panel"><h4>Participation</h4><p>Members: ${stats.total_members || 0}</p><p>Attendance marked: ${stats.attendance_marked || 0}</p></div></div>`; }
async function adminForms() {
  const [forms, events] = await Promise.all([json("/api/forms", { headers: headers() }), json("/api/events", { headers: headers() })]);
  document.getElementById("dashboard-panel").innerHTML = `<h3>📝 Registration Forms Management</h3><form id="create-form" class="form-grid"><label>Form ID *<input name="form_id" value="FORM-${String(forms.length + 1).padStart(3, "0")}" required></label><label>Event *<select name="event_id">${events.map((event) => `<option value="${esc(event.event_id)}" data-title="${esc(event.title)}">${esc(event.event_id)} - ${esc(event.title)}</option>`).join("")}</select></label><label>Form Type<select name="form_type"><option>Volunteer</option><option>Attendee</option></select></label><label>Max Seats (0 = unlimited)<input name="max_seats" type="number" min="0" value="0"></label><label>Open Date/Time<input name="open_time" placeholder="YYYY-MM-DD HH:MM:SS"></label><label>Close Date/Time<input name="close_time" placeholder="YYYY-MM-DD HH:MM:SS"></label><label style="grid-column:1/-1">Description *<textarea name="description" required></textarea></label><label><span>Open immediately</span><input name="is_open_manual" type="checkbox" checked></label><div class="actions"><button class="button" type="submit">Create Form</button></div></form><hr><h3>Existing Forms</h3>${forms.map((f) => `<div class="card" style="padding:14px;margin:10px 0"><strong>${esc(f.form_id)} - ${esc(f.event_title)}</strong><p class="caption">${esc(f.description)}</p><span class="status ${f.computed_is_open ? "open" : "closed"}">${esc(f.status_message)}</span><div class="actions"><button class="button small secondary toggle-form" data-id="${esc(f.form_id)}" data-open="${f.is_open_manual}">${f.is_open_manual ? "🔴 Close" : "🟢 Open"}</button><button class="button small danger delete-form" data-id="${esc(f.form_id)}">Delete</button></div></div>`).join("")}`;
  document.getElementById("create-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = new FormData(event.target); const selected = event.target.event_id.selectedOptions[0]; const payload = { form_id: data.get("form_id").trim(), event_id: data.get("event_id"), event_title: selected.dataset.title, form_type: data.get("form_type"), description: data.get("description").trim(), is_open_manual: data.get("is_open_manual") === "on", open_time: data.get("open_time").trim(), close_time: data.get("close_time").trim(), max_seats: Number(data.get("max_seats")) || null, created_at: new Date().toISOString().slice(0, 19).replace("T", " ") }; try { await json("/api/forms", { method: "POST", body: JSON.stringify(payload), headers: headers(true) }); notify("Form created."); adminForms(); } catch (error) { notify(error.message, "error"); } });
  document.querySelectorAll(".toggle-form").forEach((button) => button.addEventListener("click", async () => { try { await json(`/api/forms/${encodeURIComponent(button.dataset.id)}`, { method: "PUT", body: JSON.stringify({ is_open_manual: button.dataset.open !== "true" }), headers: headers(true) }); notify("Form status updated."); adminForms(); } catch (error) { notify(error.message, "error"); } }));
  document.querySelectorAll(".delete-form").forEach((button) => button.addEventListener("click", async () => { try { await api(`/api/forms/${encodeURIComponent(button.dataset.id)}`, { method: "DELETE", headers: headers() }); notify("Form deleted."); adminForms(); } catch (error) { notify(error.message, "error"); } }));
}
async function adminData() { renderDataPanel(["members", "volunteers", "attendees", "events", "attendance", "assignments", "cabinet"]); }
async function renderDataPanel(options) {
  document.getElementById("dashboard-panel").innerHTML = `<h3>🗄️ Master Database & DSA Engine</h3><div class="form-grid"><label>Dataset<select id="dataset">${options.map((option) => `<option>${option}</option>`).join("")}</select></label><label>Search Field<input id="search-key" value="name"></label><label>Search Value<input id="search-value"></label><label>Search Algorithm<select id="search-algo"><option value="linear">Linear Search</option><option value="binary">Binary Search</option></select></label><label>Sort Algorithm<select id="sort-algo"><option value="merge">Merge Sort</option><option value="quick">Quick Sort</option><option value="bubble">Bubble Sort</option><option value="insertion">Insertion Sort</option></select></label><label>Sort Key<input id="sort-key" value="name"></label><label>Order<select id="sort-reverse"><option value="false">Ascending</option><option value="true">Descending</option></select></label></div><div class="actions"><button class="button" id="run-search">🔍 Run Search</button><button class="button secondary" id="run-sort">🔃 Run Sort</button></div><div id="data-result" class="loading">Loading records…</div>`;
  const load = async (resultPromise, info = "") => { try { const result = await resultPromise; const rows = result.results || result; document.getElementById("data-result").innerHTML = `${info ? `<div class="notice">${esc(info)}</div>` : ""}${table(rows, Object.keys(rows[0] || {}).slice(0, 8).map((key) => ({ key, label: key })))} `; } catch (error) { document.getElementById("data-result").innerHTML = `<div class="notice error">${esc(error.message)}</div>`; } };
  const endpoint = (dataset) => ({ volunteers: "/api/submissions/volunteers", attendees: "/api/submissions/attendees", registrations: "/api/submissions/registrations", events: "/api/events", attendance: "/api/attendance", assignments: "/api/assignments", cabinet: "/api/admin/cabinet", members: "/api/members" }[dataset]);
  load(json(endpoint(document.getElementById("dataset").value), { headers: headers() }));
  document.getElementById("run-search").addEventListener("click", () => { const dataset = document.getElementById("dataset").value; load(json("/api/dsa/search", { method: "POST", body: JSON.stringify({ dataset, key: document.getElementById("search-key").value, query: document.getElementById("search-value").value, algorithm: document.getElementById("search-algo").value, partial: true }), headers: headers(true) }), "DSA search completed."); });
  document.getElementById("run-sort").addEventListener("click", () => { const dataset = document.getElementById("dataset").value; load(json("/api/dsa/sort", { method: "POST", body: JSON.stringify({ dataset, key: document.getElementById("sort-key").value, algorithm: document.getElementById("sort-algo").value, reverse: document.getElementById("sort-reverse").value === "true" }), headers: headers(true) }), "DSA sort completed."); });
}
async function adminCabinet() {
  const accounts = await json("/api/admin/cabinet", { headers: headers() });
  document.getElementById("dashboard-panel").innerHTML = `<h3>👥 Cabinet Portfolio Management</h3>${table(accounts, ["username", "full_name", "title", "role", "status", "email"].map((key) => ({ key, label: key })))}<hr><h4>➕ Add New Cabinet Position</h4><form id="cabinet-form" class="form-grid"><label>Username *<input name="username" required></label><label>Full Name *<input name="full_name" required></label><label>Title *<input name="title" required></label><label>Password *<input name="password" type="password" required></label><label>Email<input name="email" type="email"></label><label>Phone<input name="phone"></label><div class="actions"><button class="button" type="submit">Create Account</button></div></form>`;
  document.getElementById("cabinet-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { await json("/api/admin/cabinet", { method: "POST", body: JSON.stringify(data), headers: headers(true) }); notify("Cabinet account created."); adminCabinet(); } catch (error) { notify(error.message, "error"); } });
}
async function adminAllowed() { const rolls = await json("/api/admin/allowed-rolls", { headers: headers() }); document.getElementById("dashboard-panel").innerHTML = `<h3>📜 Allowed Roll Numbers</h3><p class="caption">${rolls.count} allowed roll numbers loaded.</p><div class="card" style="padding:14px;max-height:260px;overflow:auto">${rolls.allowed_roll_numbers.map(esc).join("<br>")}</div><form id="roll-form" class="actions"><input name="file" type="file" accept=".csv" required><button class="button" type="submit">Upload CSV</button></form>`; document.getElementById("roll-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = new FormData(event.target); try { await api("/api/admin/upload-allowed-rolls", { method: "POST", body: data, headers: headers() }); notify("Allowed roll numbers updated."); adminAllowed(); } catch (error) { notify(error.message, "error"); } }); }
async function downloadLink(path, filename) { try { const response = await api(path, { headers: headers() }); const blob = await response.blob(); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href); } catch (error) { notify(error.message, "error"); } }
async function adminAudit() { const [logs, forms] = await Promise.all([json("/api/admin/audit-log?limit=80", { headers: headers() }), json("/api/forms", { headers: headers() })]); document.getElementById("dashboard-panel").innerHTML = `<h3>💾 Audit & Download Center</h3><div class="actions"><button class="button" id="download-excel">📗 records.xlsx</button><button class="button secondary" id="download-zip">🗂️ ID Cards ZIP</button><button class="button secondary" id="download-log">📄 Activity Log</button></div><hr><h4>📥 Event Excel Download & Reset</h4><p class="caption">Download an event's data as Excel. All stored data for that event will be automatically cleared after download.</p><div class="actions"><select id="event-dl-select">${forms.map(f => `<option value="${esc(f.form_id)}">${esc(f.form_id)} - ${esc(f.event_title)}</option>`).join("")}</select><button class="button" id="download-event-btn">📗 Download Event Excel & Clear Data</button></div>${table(logs, Object.keys(logs[0] || {}).map((key) => ({ key, label: key })))} `; document.getElementById("download-excel").onclick = () => downloadLink("/api/admin/download/records-excel", "ddss_records.xlsx"); document.getElementById("download-zip").onclick = () => downloadLink("/api/admin/download/id-cards-zip", "ddss_id_cards.zip"); document.getElementById("download-log").onclick = () => downloadLink("/api/admin/download/activity-log", "activity_log.txt"); document.getElementById("download-event-btn").onclick = async () => { const sel = document.getElementById("event-dl-select"); if (!sel || !sel.value) return notify("No event selected.", "error"); await downloadLink(`/api/admin/download/event-excel/${encodeURIComponent(sel.value)}`, `event_${sel.value}.xlsx`); notify(`Event ${sel.value} data downloaded and cleared successfully.`, "success"); }; }
async function renderCabinet() {
  dashboardShell(`🎖️ Welcome, ${esc(state.user.full_name)}`, `Portfolio: ${esc(state.user.title || "Cabinet Member")} · @${esc(state.user.username)}`, [{ id: "queue", label: "📥 FIFO Queue" }, { id: "registrations", label: "🔍 Registrations" }, { id: "attendance", label: "📋 Attendance" }, { id: "assignments", label: "📌 Tasks" }, { id: "reports", label: "📊 Reports" }]);
  window.dashboardTabs = { queue: cabinetQueue, registrations: cabinetRegistrations, attendance: cabinetAttendance, assignments: cabinetAssignments, reports: cabinetReports };
  try { document.getElementById("dashboard-stats").innerHTML = metricGrid(await loadStats()); cabinetQueue(); } catch (error) { document.getElementById("dashboard-stats").innerHTML = `<div class="notice error">${esc(error.message)}</div>`; }
}
async function cabinetQueue() { const data = await json("/api/queue", { headers: headers() }); const next = data.items[0]; document.getElementById("dashboard-panel").innerHTML = `<h3>📥 Form Submissions Processing Queue (FIFO)</h3><p>Items in queue: <strong>${data.size}</strong></p>${next ? `<div class="card" style="padding:15px"><h4>⭐ Next: ${esc(next.candidate_name)} (${esc(next.roll_no)})</h4><p>Reference: ${esc(next.submission_id)} · Event: ${esc(next.event_title)} · Submitted: ${esc(next.submitted_at)}</p><div class="actions"><button class="button success process-queue" data-decision="Approved">✅ Approve</button><button class="button danger process-queue" data-decision="Rejected">❌ Reject</button></div></div>` : '<div class="notice success">🎉 All submissions have been processed.</div>'}${table(data.items.slice(1), ["submission_id", "candidate_name", "roll_no", "event_title", "submitted_at"].map((key) => ({ key, label: key })))} `; document.querySelectorAll(".process-queue").forEach((button) => button.onclick = async () => { try { await json("/api/queue/process", { method: "POST", body: formData({ decision: button.dataset.decision }), headers: headers() }); notify(`Submission ${button.dataset.decision.toLowerCase()}.`); cabinetQueue(); } catch (error) { notify(error.message, "error"); } }); }
async function cabinetRegistrations() { renderDataPanel(["volunteers", "attendees", "registrations"]); const result = document.getElementById("data-result"); result.insertAdjacentHTML("beforebegin", '<p class="caption">Use the DSA controls to search or sort registration records.</p>'); }
async function cabinetAttendance() { const events = await json("/api/events", { headers: headers() }); document.getElementById("dashboard-panel").innerHTML = `<h3>📋 Mark Event Attendance</h3><form id="attendance-form" class="form-grid"><label>Event<select name="event_id">${events.map((e) => `<option value="${esc(e.event_id)}">${esc(e.event_id)} - ${esc(e.title)}</option>`).join("")}</select></label><label>Student Roll Number *<input name="roll_no" required></label><label>Role<select name="role"><option>Attendee</option><option>Volunteer</option></select></label><label>Status<select name="status"><option>Present</option><option>Absent</option></select></label><div class="actions"><button class="button" type="submit">✅ Record Attendance</button></div></form><div id="attendance-list"></div>`; loadAttendance(); document.getElementById("attendance-form").onsubmit = async (event) => { event.preventDefault(); try { await json("/api/attendance", { method: "POST", body: new FormData(event.target), headers: headers() }); notify("Attendance recorded."); loadAttendance(); } catch (error) { notify(error.message, "error"); } }; async function loadAttendance() { const rows = await json("/api/attendance", { headers: headers() }); document.getElementById("attendance-list").innerHTML = table(rows, ["attendance_id", "event_title", "roll_no", "candidate_name", "role", "status", "marked_at"].map((key) => ({ key, label: key }))); } }
async function cabinetAssignments() { const events = await json("/api/events", { headers: headers() }); const rows = await json("/api/assignments", { headers: headers() }); document.getElementById("dashboard-panel").innerHTML = `<h3>📌 Volunteer Task Assignments</h3><form id="assignment-form" class="form-grid"><label>Event<select name="event_id">${events.map((e) => `<option value="${esc(e.event_id)}">${esc(e.event_id)} - ${esc(e.title)}</option>`).join("")}</select></label><label>Volunteer Roll Number *<input name="volunteer_roll_no" required></label><label style="grid-column:1/-1">Task Description *<textarea name="task_description" required></textarea></label><div class="actions"><button class="button" type="submit">Assign Task</button></div></form>${table(rows, ["assignment_id", "event_title", "volunteer_roll_no", "volunteer_name", "task_description", "status"].map((key) => ({ key, label: key })))} `; document.getElementById("assignment-form").onsubmit = async (event) => { event.preventDefault(); try { await json("/api/assignments", { method: "POST", body: new FormData(event.target), headers: headers() }); notify("Task assigned."); cabinetAssignments(); } catch (error) { notify(error.message, "error"); } }; }
async function cabinetReports() { const rows = await json("/api/submissions/registrations", { headers: headers() }); document.getElementById("dashboard-panel").innerHTML = `<h3>📊 Event Reports</h3><div class="actions"><button class="button" id="report-excel">📗 Download records.xlsx</button><button class="button secondary" id="report-csv">📄 Download Registrations CSV</button></div>${table(rows, Object.keys(rows[0] || {}).map((key) => ({ key, label: key })))} `; document.getElementById("report-excel").onclick = () => downloadLink("/api/admin/download/records-excel", "ddss_records.xlsx"); document.getElementById("report-csv").onclick = () => { const csv = [Object.keys(rows[0] || {}).join(","), ...rows.map((row) => Object.values(row).map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(","))].join("\n"); const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); link.download = "ddss_registrations.csv"; link.click(); }; }
render();
