// Coffee Chat Copilot front end (no build step, plain JS)
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const AGENT_COLORS = { Guard: "#b3261e", Intake: "#2a78d6", Scheduler: "#eb6834", Validator: "#1f7a4d", Responder: "#6250d6", Orchestrator: "#7b808a" };
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const state = { threads: [], selected: null, weekStart: null, nycDay: null, mood: 3, profile: null, status: null };

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.text();
}
function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (bad ? " bad" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), 4200);
}
const fmtTime = (iso) => new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
const fmtDay = (iso) => new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" });
const money = (x) => x >= 1 ? "$" + x.toFixed(2) : x >= 0.01 ? "$" + x.toFixed(3) : "$" + x.toFixed(5);
const num = (x) => Math.round(x).toLocaleString();
function nyDateStr(d = new Date()) { return d.toLocaleDateString("en-CA", { timeZone: "America/New_York" }); }
function localInputNow() { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); }

// ------------------------------------------------------------------ tabs
document.querySelectorAll(".side nav button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
function showTab(name) {
  document.querySelectorAll(".side nav button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + name));
  ({ calendar: loadCalendar, nyc: loadNyc, wellbeing: loadWellbeing, usage: loadUsage, settings: loadSettings }[name] || (() => {}))();
}

// ------------------------------------------------------------------ status
async function loadStatus() {
  const s = await api("/api/status");
  state.status = s;
  const b = $("#mode-badge");
  b.textContent = s.demo_mode ? "Demo mode (no API key)" : `Live: ${s.model} via ${s.provider}`;
  b.className = "badge " + (s.demo_mode ? "demo" : "live");
  const pct = Math.min(100, (100 * s.tokens_today) / s.daily_token_budget);
  $("#budget-bar").style.width = pct + "%";
  $("#budget-text").textContent = `${num(s.tokens_today)} / ${num(s.daily_token_budget)} tokens today`;
}

// ------------------------------------------------------------------ inbox
async function loadSamples() {
  const list = await api("/api/samples");
  $("#sample-list").innerHTML = "";
  list.forEach((s) => {
    const b = document.createElement("button");
    b.textContent = s.name; b.onclick = () => { $("#email-in").value = s.text; $("#received-at").value = localInputNow(); };
    $("#sample-list").appendChild(b);
  });
}
$("#received-at").value = localInputNow();
document.querySelectorAll("#compose-seg button").forEach((b) => (b.onclick = () => {
  document.querySelectorAll("#compose-seg button").forEach((x) => x.classList.toggle("sel", x === b));
  ["email", "outreach", "event"].forEach((k) => $("#c-" + k).classList.toggle("hidden", k !== b.dataset.c));
}));
function setCompose(k) { document.querySelector(`#compose-seg button[data-c="${k}"]`).click(); }

async function busy(btn, label, steps, fn) {
  const old = btn.textContent; btn.disabled = true; btn.textContent = label;
  const prog = $("#progress"); prog.classList.remove("hidden");
  let i = 0; prog.innerHTML = `<div class="step">${steps[0]}</div>`;
  const timer = setInterval(() => { i = Math.min(i + 1, steps.length - 1); prog.innerHTML = `<div class="step">${steps[i]}</div>`; }, 1400);
  try { return await fn(); }
  catch (e) { toast(e.message, true); }
  finally { clearInterval(timer); prog.classList.add("hidden"); btn.disabled = false; btn.textContent = old; loadStatus(); }
}
const STEPS_IN = ["Guard: scanning for prompt injection", "Intake agent: reading the email", "Scheduler agent: checking classes, trains, travel", "Validator: re-checking every time", "Responder agent: filling your club template"];
const STEPS_OUT = ["Scheduler agent: finding 90-minute windows", "Validator: classes, holds, trains, travel", "Responder agent: filling your club template"];

async function sendEmail(text, recvIso, threadId, btn) {
  const th = await busy(btn, "Working…", STEPS_IN, () => api("/api/inbox", { method: "POST", body: JSON.stringify({ email: text, received_at: recvIso, thread_id: threadId || null }) }));
  if (th) { state.selected = th.id; await loadThreads(); const st = th.steps[th.steps.length - 1]; toast(st.error ? st.error : `Draft ready in ${st.draft_ready_seconds}s`, !!st.error); }
  return th;
}
$("#btn-draft").onclick = async () => {
  const email = $("#email-in").value.trim();
  if (!email) return toast("Paste the banker's email first", true);
  const recv = $("#received-at").value ? new Date($("#received-at").value).toISOString() : null;
  if (await sendEmail(email, recv, null, $("#btn-draft"))) { $("#email-in").value = ""; $("#received-at").value = localInputNow(); }
};
$("#btn-outreach").onclick = async () => {
  if (!$("#o-name").value.trim()) return toast("Add the banker's name", true);
  const body = { banker_name: $("#o-name").value, bank: $("#o-bank").value, event: $("#o-event").value || null, referrer: $("#o-ref").value || null, mode: $("#o-mode").value, banker_email: $("#o-email").value || null };
  const th = await busy($("#btn-outreach"), "Working…", STEPS_OUT, () => api("/api/outreach", { method: "POST", body: JSON.stringify(body) }));
  if (th) { state.selected = th.id; ["#o-name", "#o-event", "#o-ref", "#o-email"].forEach((k) => ($(k).value = "")); await loadThreads(); toast("Outreach drafted. Three windows are on hold."); }
};
$("#btn-event").onclick = async () => {
  if (!$("#e-name").value.trim() || !$("#e-notes").value.trim()) return toast("Add the speaker's name and what stood out", true);
  const body = { banker_name: $("#e-name").value, bank: $("#e-bank").value, event: $("#e-event").value || "info session", notes: $("#e-notes").value, when: $("#e-when").value || "yesterday" };
  const th = await busy($("#btn-event"), "Writing…", ["Responder agent: writing from your notes", "Draft checker"], () => api("/api/event_thank_you", { method: "POST", body: JSON.stringify(body) }));
  if (th) { state.selected = th.id; $("#e-notes").value = ""; await loadThreads(); }
};
$("#btn-reset").onclick = async () => {
  if (!confirm("Clear all threads, holds, and check-ins?")) return;
  await api("/api/reset", { method: "POST" }); state.selected = null; loadThreads();
  $("#thread-detail").innerHTML = '<div class="card"><p class="muted">Cleared.</p></div>';
};

const STATUS = { reply_needed: ["reply needed", "warn"], draft_outreach: ["outreach drafted", "warn"], awaiting_banker: ["waiting on banker", ""], scheduled: ["chat scheduled", "good"], done: ["done", ""], new: ["new", ""] };
async function loadThreads() {
  state.threads = await api("/api/threads");
  const pend = state.threads.filter((t) => t.status === "reply_needed" || t.follow_up_ready).length;
  $("#nav-pending").textContent = pend; $("#nav-pending").classList.toggle("hidden", !pend);
  const el = $("#thread-list");
  if (!state.threads.length) { el.innerHTML = '<p class="muted">No bankers yet. Reach out after an event, or paste a banker\'s email.</p>'; return; }
  el.innerHTML = state.threads.map((t) => {
    const [txt, cls] = STATUS[t.status] || [t.status, ""];
    return `<div class="thread ${t.id === state.selected ? "sel" : ""}" data-id="${t.id}">
      <div class="t1"><span>${esc(t.banker_name || "Unknown banker")}</span><span class="small muted">${fmtDay(t.updated_at)}</span></div>
      <div class="t2">${esc(t.bank || "")}
        <span class="chip ${t.mode === "in_person" ? "inp" : ""}">${t.mode === "in_person" ? "in person" : esc(t.mode || "")}</span>
        <span class="chip ${cls}">${txt}</span>
        ${t.follow_up_ready ? '<span class="chip bad">follow up</span>' : ""}
        ${t.suspicious ? '<span class="chip bad">suspicious</span>' : ""}
      </div></div>`;
  }).join("");
  el.querySelectorAll(".thread").forEach((d) => (d.onclick = () => { state.selected = d.dataset.id; loadThreads(); }));
  const sel = state.threads.find((t) => t.id === state.selected);
  if (sel) renderThread(sel);
}

const KIND_TITLE = { inbound: "Banker's email + your reply", outreach: "Your outreach", follow_up: "Follow-up (no response)", running_late: "Running-late note", thank_you: "Thank-you note" };
const TPL_NAME = { availability_reply: "availability reply", outreach_intro: "outreach (with intro)", outreach_no_intro: "outreach (no intro)", follow_up_no_response: "no-response follow-up", time_conflict: "time conflict", invite_virtual: "invite (virtual)", invite_in_person: "invite (in person)", running_late: "running late", thank_you_post_chat: "thank-you (after chat)", thank_you_post_event: "thank-you (after event)", thank_you_for_intro: "thank you for intro" };
let slaTimer = null;
function renderThread(t) {
  clearInterval(slaTimer);
  const steps = (t.steps || []).slice().reverse();
  const latest = steps[0];
  const [txt, cls] = STATUS[t.status] || [t.status, ""];
  $("#thread-detail").innerHTML = `
    <div class="card">
      <div class="row between"><div><h3 style="margin:0">${esc(t.banker_name || "Unknown banker")} <span class="muted">· ${esc(t.bank || "bank unknown")}</span></h3>
        <p class="small muted" style="margin-top:4px"><span class="chip ${cls}">${txt}</span> ${t.event ? "Met at " + esc(t.event) : ""} ${t.referrer ? "· referred by " + esc(t.referrer) : ""}</p></div>
        <button class="ghost small danger" id="del-th">Delete</button></div>
      <div style="height:12px"></div>
      <div class="next-box" id="next-box"></div>
    </div>
    <div class="convo">${steps.map((st, i) => stepHtml(t, st, i === 0)).join("")}</div>`;
  renderNext(t, latest);
  steps.forEach((st) => bindStep(t, st));
  // SLA countdown for the newest inbound email
  const sla = $("#sla-" + (latest && latest.id));
  if (sla && latest.kind === "inbound") {
    const tick = () => {
      if (latest.sent_at) { sla.className = "sla done"; sla.innerHTML = `<div class="clock">Sent</div><div>Replied ${latest.reply_minutes} min after the email arrived. Club rule is 15 min.</div>`; return; }
      const left = (new Date(latest.deadline) - new Date()) / 1000;
      const mm = Math.floor(Math.abs(left) / 60), ss = String(Math.floor(Math.abs(left) % 60)).padStart(2, "0");
      sla.className = "sla " + (left < 0 ? "late" : left < 180 ? "urgent" : "");
      sla.innerHTML = left >= 0 ? `<div class="clock">${mm}:${ss}</div><div>left to reply (club rule: 15 min).<br><span class="small muted">Draft was ready ${latest.draft_ready_seconds ?? "?"}s after you pasted it.</span></div>`
        : `<div class="clock">-${mm}:${ss}</div><div>Past the 15-minute window. Send it now.</div>`;
    };
    tick(); slaTimer = setInterval(tick, 1000);
  }
  $("#del-th").onclick = async () => { if (!confirm("Delete this banker and release their holds?")) return; await api(`/api/threads/${t.id}`, { method: "DELETE" }); state.selected = null; $("#thread-detail").innerHTML = ""; loadThreads(); };
}
function renderNext(t, latest) {
  const box = $("#next-box");
  const name = esc(t.banker_first_name || t.banker_name || "the banker");
  let html = "";
  if (t.status === "awaiting_banker") {
    html += `<b>Waiting on ${name}.</b> <span class="small muted">${t.follow_up_due ? "Follow-up due " + fmtDay(t.follow_up_due) : ""}</span>
      <div class="actions"><button class="${t.follow_up_ready ? "primary" : ""} small" id="nx-follow">Draft follow-up${t.follow_up_ready ? "" : " early"}</button></div>`;
  }
  if (t.status === "scheduled") {
    html += `<b>Chat scheduled.</b> Day of: send a running-late note in one tap. After: write the thank-you.
      <div class="actions"><input id="nx-loc" placeholder="lobby at 55 E 52nd St" style="flex:1"><button class="small" id="nx-late">Running-late note (no AI)</button></div>
      <textarea id="nx-notes" rows="3" placeholder="2-3 things you talked about (e.g. his move into Consumer & Retail; advice on curveball and C&R questions)" style="margin-top:10px"></textarea>
      <div class="actions"><input id="nx-when" value="yesterday" style="width:120px"><button class="primary small" id="nx-thanks">Draft thank-you</button></div>`;
  }
  html += `<details ${t.status === "awaiting_banker" ? "open" : ""} style="margin-top:10px"><summary class="small" style="cursor:pointer;color:var(--yale)">Paste ${name}'s reply</summary>
      <textarea id="nx-reply" rows="5" placeholder="Paste the banker's reply here…" style="margin-top:8px"></textarea>
      <button class="primary small" id="nx-reply-go">Draft reply</button></details>`;
  box.innerHTML = html;
  const fu = $("#nx-follow");
  if (fu) fu.onclick = async () => { const th = await busy(fu, "Working…", STEPS_OUT, () => api(`/api/threads/${t.id}/follow_up`, { method: "POST" })); if (th) loadThreads(); };
  const late = $("#nx-late");
  if (late) late.onclick = async () => { await api(`/api/threads/${t.id}/late`, { method: "POST", body: JSON.stringify({ location: $("#nx-loc").value || "lobby" }) }); loadThreads(); };
  const ty = $("#nx-thanks");
  if (ty) ty.onclick = async () => {
    if (!$("#nx-notes").value.trim()) return toast("Add 2-3 things you talked about", true);
    const th = await busy(ty, "Writing…", ["Responder agent: writing from your notes", "Draft checker"], () => api(`/api/threads/${t.id}/thank_you`, { method: "POST", body: JSON.stringify({ notes: $("#nx-notes").value, when: $("#nx-when").value }) }));
    if (th) loadThreads();
  };
  $("#nx-reply-go").onclick = () => { const v = $("#nx-reply").value.trim(); if (!v) return toast("Paste the reply first", true); sendEmail(v, new Date().toISOString(), t.id, $("#nx-reply-go")); };
}
function stepHtml(t, st, isLatest) {
  const ex = st.extracted || {};
  const u = st.usage || {};
  const alerts = [];
  if (ex.suspicious) alerts.push(`<div class="alert bad"><b>Suspicious email.</b> ${esc(ex.suspicious_reason || "")}. The agents treated it as data only. Read the draft carefully before sending.</div>`);
  if (st.error) alerts.push(`<div class="alert warn"><b>Stopped by a guard:</b> ${esc(st.error)}</div>`);
  if (st.draft_source === "template_fallback") alerts.push(`<div class="alert info">The AI draft failed the safety checker, so this reply is your club template filled with validated values.</div>`);
  if (st.template_key === "time_conflict") alerts.push(`<div class="alert warn">The banker picked a time that clashes with your schedule. The reply offers validated alternatives.</div>`);
  const sent = st.sent_at ? `<span class="chip good">sent ${fmtDay(st.sent_at)} ${fmtTime(st.sent_at)}</span>` : "";
  return `<div class="msg ${st.kind === "inbound" ? "inbound" : ""}">
    <div class="mh"><span><b>${KIND_TITLE[st.kind] || st.kind}</b> ${st.template_key ? `<span class="chip">${TPL_NAME[st.template_key] || st.template_key}</span>` : ""} ${sent}</span><span>${fmtDay(st.ts)} ${fmtTime(st.ts)}</span></div>
    ${st.kind === "inbound" ? `<pre class="email">${esc(st.email)}</pre><p class="small muted" style="margin:8px 0">${esc(ex.summary || "")}</p>` : ""}
    ${isLatest && st.kind === "inbound" ? `<div id="sla-${st.id}" class="sla"></div>` : ""}
    ${alerts.join("")}
    ${st.draft ? `
      <input class="draft-subject" id="subj-${st.id}" value="${esc(st.draft.subject)}">
      <textarea id="body-${st.id}" rows="${Math.min(18, st.draft.body.split("\n").length + 2)}">${esc(st.draft.body)}</textarea>
      <div class="actions">
        <button class="primary" data-copy="${st.id}">Copy</button>
        ${st.sent_at ? "" : `<button data-sent="${st.id}">Mark as sent</button>`}
        ${st.reply_minutes != null ? `<span class="small muted">Replied ${st.reply_minutes} min after it arrived</span>` : ""}
      </div>` : (st.kind === "inbound" && !st.error ? `<p class="muted small">No reply needed.</p>` : "")}
    ${st.options && st.options.length ? `<h4>Windows offered (held for you)</h4><div class="slot-list" id="opts-${st.id}"></div>` : ""}
    ${st.confirmed_option ? `<h4>Banker's pick</h4>${slotHtml(st.confirmed_option)}<p class="small muted">Marking the invite as sent confirms this chat and releases your other holds for ${esc(t.banker_first_name || "this banker")}.</p>` : ""}
    ${st.suggested_outreach ? `<div class="next-box" style="margin-top:10px"><b>Next:</b> reach out to ${esc(st.suggested_outreach.banker_name || "the new contact")} (referred by ${esc(st.suggested_outreach.referrer || "")}). <button class="small primary" data-suggest="${st.id}">Draft outreach</button></div>` : ""}
    <details style="margin-top:10px"><summary class="small muted" style="cursor:pointer">What the agents did · ${u.llm_calls ?? 0} model calls · ${num((u.input_tokens || 0) + (u.output_tokens || 0))} tokens · ${money(u.cost_usd || 0)} · ${u.seconds ?? 0}s</summary>
      <div class="usage-line" style="margin:8px 0"><span>Input <b>${num(u.input_tokens || 0)}</b></span><span>Cached <b>${num(u.cached_tokens || 0)}</b></span><span>Cache write <b>${num(u.cache_write_tokens || 0)}</b></span><span>Output <b>${num(u.output_tokens || 0)}</b></span></div>
      <div class="trace">${(st.trace || []).map((e) => `<div class="ev" style="--c:${AGENT_COLORS[e.agent] || "#999"}"><b>${esc(e.agent)}</b> <span class="small muted">${esc(e.step)}</span><div class="d">${esc(e.detail)}</div>${e.data && (Array.isArray(e.data) ? e.data.length : Object.keys(e.data).length) ? `<details><summary>details</summary><pre>${esc(JSON.stringify(e.data, null, 2))}</pre></details>` : ""}</div>`).join("")}</div>
    </details>
  </div>`;
}
function bindStep(t, st) {
  const c = document.querySelector(`[data-copy="${st.id}"]`);
  if (c) c.onclick = async () => {
    const txt = `Subject: ${$("#subj-" + st.id).value}\n\n${$("#body-" + st.id).value}`;
    try { await navigator.clipboard.writeText(txt); toast("Copied. Paste it into Outlook."); } catch (_) { $("#body-" + st.id).select(); document.execCommand("copy"); toast("Copied"); }
  };
  const s = document.querySelector(`[data-sent="${st.id}"]`);
  if (s) s.onclick = async () => { await api(`/api/threads/${t.id}/steps/${st.id}/sent`, { method: "POST" }); toast("Marked as sent"); loadThreads(); };
  const g = document.querySelector(`[data-suggest="${st.id}"]`);
  if (g) g.onclick = () => {
    const so = st.suggested_outreach; setCompose("outreach");
    $("#o-name").value = so.banker_name || ""; $("#o-ref").value = so.referrer || ""; $("#o-email").value = so.banker_email || "";
    if (so.bank) $("#o-bank").value = so.bank;
    $("#o-name").focus(); toast("Outreach form filled in. Check it, then click Draft outreach.");
  };
  if (st.options && st.options.length) {
    api("/api/holds").then((holds) => {
      const el = $("#opts-" + st.id); if (!el) return;
      el.innerHTML = st.options.map((o) => slotHtml(o, holds.find((h) => h.thread_id === t.id && h.start === o.start))).join("");
      bindHoldButtons(el);
    });
  }
}
function slotHtml(o, h) {
  const trip = o.trip ? `Leave campus ${o.trip.leave_campus} · Train ${o.trip.train_out.depart}→${o.trip.train_out.arrive} · Back ${o.trip.train_back.depart}→${o.trip.train_back.arrive} · Home ${o.trip.back_on_campus}`
    : o.offer_mode === "either" ? "Works in person too (NYC trip fits around classes)" : "Virtual / phone: no travel";
  const st = h ? h.status : null;
  return `<div class="slot ${st === "confirmed" ? "confirmed" : ""}"><div><div class="s1">${esc(o.label)}</div><div class="s2">${esc(trip)}</div>${o.why ? `<div class="s2"><i>${esc(o.why)}</i></div>` : ""}</div>
    <div class="row">${h ? (st === "confirmed" ? '<span class="chip good">confirmed</span>' : `<button class="small good" data-confirm="${h.id}">Banker picked this</button>`) + ` <a class="small" href="/api/ics/${h.id}">.ics</a>` : ""}</div></div>`;
}
function bindHoldButtons(root) {
  root.querySelectorAll("[data-confirm]").forEach((b) => (b.onclick = async () => {
    await api(`/api/holds/${b.dataset.confirm}/confirm`, { method: "POST" });
    toast("Confirmed. The other holds for this banker are released.");
    loadThreads(); if ($("#tab-calendar").classList.contains("active")) loadCalendar();
  }));
  root.querySelectorAll("[data-release]").forEach((b) => (b.onclick = async () => {
    await api(`/api/holds/${b.dataset.release}/release`, { method: "POST" }); loadCalendar();
  }));
}

// ------------------------------------------------------------------ calendar
function mondayOf(dateStr) { const d = new Date(dateStr + "T12:00:00"); const k = (d.getDay() + 6) % 7; d.setDate(d.getDate() - k); return d.toISOString().slice(0, 10); }
function addDays(s, n) { const d = new Date(s + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); }
$("#cal-prev").onclick = () => { state.weekStart = addDays(state.weekStart, -7); loadCalendar(); };
$("#cal-next").onclick = () => { state.weekStart = addDays(state.weekStart, 7); loadCalendar(); };
const H0 = 7, H1 = 24, PX = 40;
function minutesNY(iso) { const p = new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "America/New_York", hour12: false }).split(":"); return (+p[0]) * 60 + (+p[1]); }
function dateNY(iso) { return new Date(iso).toLocaleDateString("en-CA", { timeZone: "America/New_York" }); }
async function loadCalendar() {
  if (!state.weekStart) state.weekStart = mondayOf(nyDateStr());
  const cal = await api(`/api/calendar?start=${state.weekStart}&days=7`);
  const today = nyDateStr();
  $("#cal-range").textContent = `${fmtDay(state.weekStart + "T12:00:00")} – ${fmtDay(addDays(state.weekStart, 6) + "T12:00:00")}`;
  let html = '<div class="hd"></div>';
  for (let i = 0; i < 7; i++) { const d = addDays(state.weekStart, i); html += `<div class="hd ${d === today ? "today" : ""}">${DAYS[i]} ${+d.slice(8)}</div>`; }
  html += `<div class="times" style="height:${(H1 - H0) * PX}px">${Array.from({ length: H1 - H0 }, (_, i) => `<div style="top:${i * PX}px">${((H0 + i - 1) % 12) + 1}${H0 + i < 12 ? "a" : "p"}</div>`).join("")}</div>`;
  for (let i = 0; i < 7; i++) {
    const d = addDays(state.weekStart, i);
    const evs = cal.events.filter((e) => dateNY(e.start) === d).sort((a, b) => (a.kind === "travel" ? -1 : 1));
    html += `<div class="day" style="height:${(H1 - H0) * PX}px">` + evs.map((e) => {
      const s = Math.max(minutesNY(e.start), H0 * 60), en0 = minutesNY(e.end), en = Math.min(en0 <= s ? 24 * 60 : en0, H1 * 60);
      const top = ((s - H0 * 60) / 60) * PX, h = Math.max(14, ((en - s) / 60) * PX - 2);
      const title = e.kind === "held" ? `HOLD · ${e.title}` : e.title;
      return `<div class="ev-box ${e.kind}" style="top:${top}px;height:${h}px" title="${esc(title)} ${fmtTime(e.start)}–${fmtTime(e.end)}">${e.kind === "travel" ? "" : `<b>${fmtTime(e.start)}</b> ${esc(e.kind === "held" ? "Hold: " + (e.bank || "") : e.kind === "confirmed" ? (e.bank || "Chat") : e.title)}`}</div>`;
    }).join("") + "</div>";
  }
  $("#week").innerHTML = html;
  const holds = await api("/api/holds");
  $("#holds-list").innerHTML = holds.length ? holds.sort((a, b) => a.start.localeCompare(b.start)).map((h) => `
    <div class="slot ${h.status === "confirmed" ? "confirmed" : ""}"><div><div class="s1">${fmtDay(h.start)} ${fmtTime(h.start)}–${fmtTime(h.end)}</div>
    <div class="s2">${esc(h.banker || "")} · ${esc(h.bank || "")} · ${h.mode === "in_person" ? "in person" : "virtual"} ${h.status === "held" ? "· hold expires " + fmtDay(h.expires_at) + " " + fmtTime(h.expires_at) : ""}</div></div>
    <div class="row">${h.status === "held" ? `<button class="small good" data-confirm="${h.id}">Confirm</button><button class="small" data-release="${h.id}">Release</button>` : '<span class="chip good">confirmed</span>'} <a class="small" href="/api/ics/${h.id}">.ics</a></div></div>`).join("") : '<p class="muted">No holds yet.</p>';
  bindHoldButtons($("#holds-list"));
}
async function loadBanks() {
  const banks = await api("/api/banks");
  const opts = banks.map((b) => `<option value="${esc(b.name)}">${esc(b.name)} (${esc(b.address)})</option>`).join("");
  $("#qf-bank").innerHTML = opts; $("#mc-bank").innerHTML = opts; $("#o-bank").innerHTML = opts; $("#e-bank").innerHTML = opts;
}
$("#qf-go").onclick = async () => {
  const r = await api(`/api/slots?mode=${$("#qf-mode").value}&bank=${encodeURIComponent($("#qf-bank").value)}`);
  $("#qf-out").innerHTML = r.length ? r.map((o) => slotHtml(o)).join("") : '<p class="muted">No free windows in the next 10 days.</p>';
};
$("#mc-go").onclick = async () => {
  if (!$("#mc-banker").value || !$("#mc-start").value) return toast("Add a name and a start time", true);
  const r = await api("/api/holds/manual", { method: "POST", body: JSON.stringify({ banker: $("#mc-banker").value, bank: $("#mc-bank").value, mode: $("#mc-mode").value, start: new Date($("#mc-start").value).toISOString() }) });
  $("#mc-out").innerHTML = r.warnings.length ? `<span style="color:var(--bad)">Added, but watch out: ${esc(r.warnings.join("; "))}</span>` : "Added.";
  loadCalendar(); loadThreads();
};

// ------------------------------------------------------------------ NYC
$("#nyc-held").onchange = () => loadNyc();
async function loadNyc() {
  const nd = await api("/api/nyc_days"); const days = nd.days;
  if (!days.length) { $("#nyc-days").innerHTML = ""; $("#nyc-plan").innerHTML = '<p class="muted">No NYC days yet. Process an in-person banker email first.</p>'; $("#nyc-flags").innerHTML = ""; $("#nyc-meals").innerHTML = ""; return; }
  if (!state.nycDay || !days.includes(state.nycDay)) state.nycDay = nd.best || days[0];
  $("#nyc-days").innerHTML = days.map((d) => `<button class="day-chip ${d === state.nycDay ? "sel" : ""}" data-d="${d}">${fmtDay(d + "T12:00:00")}</button>`).join("");
  document.querySelectorAll(".day-chip").forEach((b) => (b.onclick = () => { state.nycDay = b.dataset.d; loadNyc(); }));
  $("#nyc-days").insertAdjacentHTML("beforeend", "<div style='height:56px'></div>");
  const p = await api(`/api/dayplan?day=${state.nycDay}&include_held=${$("#nyc-held").checked}`);
  const icon = { leave: "🎒", train: "🚆", travel: "🚶", chat: "☕", home: "🏠" };
  $("#nyc-plan").innerHTML = p.steps.length ? `<h3>${fmtDay(state.nycDay + "T12:00:00")} · leave ${p.trip.leave}, home ${p.trip.home}</h3><ul class="timeline">${p.steps.map((s) => `<li class="${s.type}"><span class="tm">${s.time}</span><span class="ic">${s.type === "travel" && s.text.startsWith("Subway") ? "🚇" : icon[s.type] || "•"}</span><span>${esc(s.text)}${s.end ? ` <span class="muted">until ${s.end}</span>` : ""}</span></li>`).join("")}</ul>
    <p class="small muted" style="margin-top:10px">Train times come from the sample timetable in data/metro_north_sample.csv. Check MTA TrainTime before you leave.</p>` : '<p class="muted">Only virtual chats on this day, or the plan has a problem (see Heads-up).</p>';
  $("#nyc-flags").innerHTML = p.flags.length ? p.flags.map((f) => `<div class="alert ${f.level === "bad" ? "bad" : f.level === "warn" ? "warn" : "info"}">${esc(f.text)}</div>`).join("") : '<p class="muted">Nothing to worry about.</p>';
  const treats = (state.profile?.wellbeing?.favorite_treats) || [];
  $("#nyc-meals").innerHTML = p.meals.map((m) => `<div class="alert info">🍽️ ${esc(m.text)}</div>`).join("") + (treats.length ? `<div class="alert info">🍵 After your last chat: ${esc(treats[0])}. You earned it.</div>` : "");
}

// ------------------------------------------------------------------ wellbeing
const MOODS = ["😫", "😕", "😐", "🙂", "😄"];
$("#mood").innerHTML = MOODS.map((m, i) => `<button data-m="${i + 1}" class="${i === 2 ? "sel" : ""}" title="mood ${i + 1}/5">${m}</button>`).join("");
document.querySelectorAll("#mood button").forEach((b) => (b.onclick = () => { state.mood = +b.dataset.m; document.querySelectorAll("#mood button").forEach((x) => x.classList.toggle("sel", x === b)); }));
$("#ci-save").onclick = async () => {
  await api("/api/checkins", { method: "POST", body: JSON.stringify({ mood: state.mood, slept_hours: +$("#ci-sleep").value, ate_well: $("#ci-ate").checked, talked_to_friend: $("#ci-friend").checked, note: $("#ci-note").value }) });
  toast("Check-in saved"); loadWellbeing();
};
$("#coach-rules").onclick = () => loadCoach(false);
$("#coach-ai").onclick = () => loadCoach(true);
const NUDGE_ICON = { food: "🍜", treat: "🍵", friends: "💬", rest: "😴", pace: "🧭", support: "🤝" };
async function loadCoach(useLlm) {
  try {
    const c = await api("/api/coach", { method: "POST", body: JSON.stringify({ use_llm: useLlm }) });
    $("#coach-head").textContent = c.headline || "Your coach";
    $("#coach-nudges").innerHTML = c.nudges.map((n) => `<div class="nudge"><span class="ic">${NUDGE_ICON[n.kind] || "✨"}</span><div>${esc(n.text)}</div></div>`).join("");
    $("#coach-src").textContent = (c.source === "coach agent" ? `Written by the coach agent · ${num((c.usage?.input_tokens || 0) + (c.usage?.output_tokens || 0))} tokens · ${money(c.usage?.cost_usd || 0)}` : "Rule-based (free)") + (c.error ? " · " + c.error : "");
    const f = c.facts;
    $("#wb-facts").innerHTML = [
      ["Confirmed chats (7 days)", f.confirmed_chats_next_7_days, `limit ${f.max_chats_per_week}/week`],
      ["NYC days", f.nyc_days.length, f.nyc_days.join(", ") || "none"],
      ["Late returns", f.late_returns.length, "back after 10 PM"],
      ["Emails waiting", f.pending_replies, "drafted, not marked sent"],
    ].map(([k, v, s]) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${esc(s)}</div></div>`).join("");
    loadStatus();
  } catch (e) { toast(e.message, true); }
}
async function loadWellbeing() {
  loadCoach(false);
  const cis = await api("/api/checkins");
  $("#ci-history").innerHTML = cis.slice(-14).map((c) => `<div class="bar" style="height:${c.mood * 14}px" data-tip="${c.date}: mood ${c.mood}/5, slept ${c.slept_hours}h"></div>`).join("") || '<span class="small muted">Your mood over the last 2 weeks will show here.</span>';
}

// ------------------------------------------------------------------ usage
$("#usage-refresh").onclick = () => loadUsage();
async function loadUsage() {
  const u = await api("/api/usage");
  const a = u.avg_inbox_run;
  const cacheRate = a.input_tokens ? (100 * a.cached_tokens) / a.input_tokens : 0;
  $("#usage-tiles").innerHTML = [
    ["Tokens per email (avg)", num(a.input_tokens + a.output_tokens), `${num(a.input_tokens)} in · ${num(a.cached_tokens)} cached · ${num(a.output_tokens)} out`],
    ["Cost per email", money(a.cost_usd), `${a.llm_calls} model calls · ${a.seconds}s · ${u.inbox_runs} emails measured`],
    ["Cache hit rate", cacheRate.toFixed(0) + "%", "share of input tokens read from cache"],
    ["Per user / month", money(u.monthly_per_user_usd), u.assumptions],
    ["100 users / month", money(u.scale["100_users"]), "a finance club"],
    ["10,000 users / month", money(u.scale["10000_users"]), "every IB recruit in the US"],
  ].map(([k, v, s]) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${esc(s)}</div></div>`).join("") +
    (u.provider === "mock" ? '<div class="tile" style="grid-column:1/-1"><div class="k">Demo mode</div><div class="s">No API key, so token counts are estimates (chars ÷ 4). Add PORTKEY_API_KEY to .env for real measured usage.</div></div>' : "");
  const agents = Object.entries(u.by_agent);
  const max = Math.max(1e-9, ...agents.map(([, v]) => v.cost_usd));
  $("#usage-chart").innerHTML = agents.length ? agents.map(([k, v]) => `<div class="hbar" title="${esc(k)}: ${money(v.cost_usd)} over ${v.calls} calls"><span>${esc(k)}</span><div class="track"><div class="fill" style="width:${(100 * v.cost_usd) / max}%"></div></div><span class="val">${money(v.cost_usd)}</span></div>`).join("") : '<p class="muted">No calls yet.</p>';
  $("#usage-agents").innerHTML = `<table><tr><th>Agent</th><th class="n">Calls</th><th class="n">Input</th><th class="n">Cached</th><th class="n">Output</th><th class="n">Cost</th></tr>${agents.map(([k, v]) => `<tr><td>${esc(k)}</td><td class="n">${v.calls}</td><td class="n">${num(v.input_tokens)}</td><td class="n">${num(v.cached_tokens)}</td><td class="n">${num(v.output_tokens)}</td><td class="n">${money(v.cost_usd)}</td></tr>`).join("")}</table>`;
  $("#usage-calls").innerHTML = `<table><tr><th>Time</th><th>Run</th><th>Agent</th><th>Provider</th><th class="n">Input</th><th class="n">Cached</th><th class="n">Cache write</th><th class="n">Output</th><th class="n">ms</th><th class="n">Cost</th></tr>${u.records.slice().reverse().map((r) => `<tr><td>${esc(r.ts.slice(5, 16).replace("T", " "))}</td><td>${esc(r.run)}</td><td>${esc(r.agent)}</td><td>${esc(r.provider)}</td><td class="n">${num(r.input_tokens)}</td><td class="n">${num(r.cached_tokens)}</td><td class="n">${num(r.cache_write_tokens)}</td><td class="n">${num(r.output_tokens)}</td><td class="n">${num(r.latency_ms)}</td><td class="n">${money(r.cost_usd)}</td></tr>`).join("")}</table>`;
}

// ------------------------------------------------------------------ settings
async function loadSettings() {
  const p = await api("/api/profile"); state.profile = p;
  $("#p-name").value = p.name; $("#p-school").value = p.school; $("#p-title").value = p.title_line || ""; $("#p-phone").value = p.phone || ""; $("#p-email").value = p.email || ""; $("#p-zoom").value = p.zoom_details || ""; $("#p-earliest").value = p.earliest_chat; $("#p-latest").value = p.latest_chat_end;
  $("#p-block").value = p.chat_block_min; $("#p-c2s").value = p.campus_to_station_min;
  $("#p-maxday").value = p.wellbeing.max_chats_per_day; $("#p-maxweek").value = p.wellbeing.max_chats_per_week;
  $("#p-treats").value = (p.wellbeing.favorite_treats || []).join(", "); $("#p-friends").value = (p.wellbeing.friends || []).join(", ");
  const cd = p.chat_days || DAYS.slice(0, 5);
  $("#p-days").innerHTML = DAYS.map((d) => `<label><input type="checkbox" value="${d}" ${cd.includes(d) ? "checked" : ""}> ${d}</label>`).join("");
  renderClasses(p.classes);
  state.templates = await api("/api/templates");
  const keys = Object.keys(state.templates);
  const cur = $("#t-key").value || keys[0];
  $("#t-key").innerHTML = keys.map((k) => `<option value="${k}">${TPL_NAME[k] || k}</option>`).join("");
  $("#t-key").value = cur; $("#t-text").value = state.templates[cur];
}
function renderClasses(classes) {
  $("#p-classes").innerHTML = classes.map((c) => `<div class="class-row"><input class="c-name" value="${esc(c.name)}" placeholder="Class"><input class="c-days" value="${esc(c.days.join(","))}" placeholder="Mon,Wed"><input class="c-start" type="time" value="${c.start}"><input class="c-end" type="time" value="${c.end}"><button class="ghost small c-del">✕</button></div>`).join("");
  document.querySelectorAll(".c-del").forEach((b) => (b.onclick = () => { b.parentElement.remove(); }));
}
$("#p-addclass").onclick = () => { const cur = readClasses(); cur.push({ name: "", days: ["Mon"], start: "09:00", end: "10:15" }); renderClasses(cur); };
function readClasses() {
  return [...document.querySelectorAll(".class-row")].map((r) => ({ name: r.querySelector(".c-name").value.trim(), days: r.querySelector(".c-days").value.split(",").map((s) => s.trim().slice(0, 1).toUpperCase() + s.trim().slice(1, 3).toLowerCase()).filter((d) => DAYS.includes(d)), start: r.querySelector(".c-start").value, end: r.querySelector(".c-end").value })).filter((c) => c.name && c.days.length && c.start && c.end);
}
$("#p-save").onclick = async () => {
  const p = state.profile;
  Object.assign(p, { name: $("#p-name").value, school: $("#p-school").value, title_line: $("#p-title").value, phone: $("#p-phone").value, email: $("#p-email").value, zoom_details: $("#p-zoom").value, earliest_chat: $("#p-earliest").value, latest_chat_end: $("#p-latest").value,
    chat_block_min: +$("#p-block").value, campus_to_station_min: +$("#p-c2s").value, station_to_campus_min: +$("#p-c2s").value,
    chat_days: [...document.querySelectorAll("#p-days input:checked")].map((x) => x.value), classes: readClasses() });
  p.wellbeing.max_chats_per_day = +$("#p-maxday").value; p.wellbeing.max_chats_per_week = +$("#p-maxweek").value;
  p.wellbeing.favorite_treats = $("#p-treats").value.split(",").map((s) => s.trim()).filter(Boolean);
  p.wellbeing.friends = $("#p-friends").value.split(",").map((s) => s.trim()).filter(Boolean);
  try { await api("/api/profile", { method: "PUT", body: JSON.stringify(p) }); $("#p-msg").textContent = "Saved."; } catch (e) { toast(e.message, true); }
};
$("#t-key").onchange = () => { $("#t-text").value = state.templates[$("#t-key").value]; $("#t-msg").textContent = ""; };
$("#t-save").onclick = async () => {
  try { await api("/api/templates", { method: "PUT", body: JSON.stringify({ key: $("#t-key").value, text: $("#t-text").value }) }); state.templates[$("#t-key").value] = $("#t-text").value; $("#t-msg").textContent = "Saved."; } catch (e) { toast(e.message, true); }
};

// ------------------------------------------------------------------ boot
(async function boot() {
  try {
    await loadStatus(); await loadSamples(); await loadThreads(); await loadBanks();
    state.profile = await api("/api/profile");
  } catch (e) { toast("Could not reach the server: " + e.message, true); }
  setInterval(loadStatus, 30000);
})();
