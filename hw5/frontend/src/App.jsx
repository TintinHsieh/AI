import { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8051";

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.detail?.message || payload?.detail || `Request failed (${response.status})`);
  return payload;
}

function Status({ value }) {
  const tone = value === "resolved" ? "success" : value === "pending_approval" ? "warning" : value === "needs_information" ? "info" : "neutral";
  return <span className={`status ${tone}`}>{String(value || "unknown").replaceAll("_", " ")}</span>;
}

function EventRow({ event }) {
  return <div className="event-row"><div className="event-dot" /><div><strong>{event.agent}</strong><span className="event-type">{event.event_type.replaceAll("_", " ")}</span><p>{event.details?.tool ? `MCP · ${event.details.tool}` : event.details?.to ? `Delegated to ${event.details.to}` : event.details?.status ? `Status: ${event.details.status}` : event.details?.request ? `Payment request #${event.details.request.id} · $${Number(event.details.request.amount).toFixed(2)}` : event.details?.error || event.details?.role || "Recorded workflow event"}</p></div></div>;
}

function App() {
  const [tickets, setTickets] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [ticketDetail, setTicketDetail] = useState(null);
  const [events, setEvents] = useState([]);
  const [cash, setCash] = useState(null);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [approving, setApproving] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selected = useMemo(() => tickets.find((ticket) => ticket.id === selectedId) || tickets[0], [tickets, selectedId]);

  async function refresh(nextId = selectedId) {
    setError("");
    const [ticketRows, cashRow, requestRows] = await Promise.all([request("/api/tickets"), request("/api/cash"), request("/api/payment-requests")]);
    setTickets(ticketRows); setCash(cashRow); setRequests(requestRows);
    const id = nextId || ticketRows[0]?.id;
    if (id) {
      setSelectedId(id);
      const [detail, audit] = await Promise.all([request(`/api/tickets/${id}`), request(`/api/audit?ticket_id=${id}`)]);
      setTicketDetail(detail); setEvents(audit);
    }
  }

  useEffect(() => { refresh().catch((err) => setError(err.message)).finally(() => setLoading(false)); }, []);

  async function selectTicket(id) {
    setSelectedId(id); setError("");
    try { const [detail, audit] = await Promise.all([request(`/api/tickets/${id}`), request(`/api/audit?ticket_id=${id}`)]); setTicketDetail(detail); setEvents(audit); }
    catch (err) { setError(err.message); }
  }

  async function runTicket() {
    if (!selected || running) return;
    setRunning(true); setError(""); setNotice("Boss is coordinating specialists through MCP…");
    try { await request(`/api/tickets/${selected.id}/run`, { method: "POST" }); await refresh(selected.id); setNotice("Run complete. Activity below is loaded from the audit trail."); }
    catch (err) { setError(err.message); setNotice(""); }
    finally { setRunning(false); }
  }

  async function approve(requestId) {
    if (approving) return;
    const approvedBy = window.prompt("Type the human approver name to execute this payment:");
    if (!approvedBy) return;
    setApproving(requestId); setError("");
    try { await request(`/api/payment-requests/${requestId}/approve`, { method: "POST", body: JSON.stringify({ approved_by: approvedBy }) }); await refresh(selectedId); setNotice("Payment approved and cash refreshed from the backend."); }
    catch (err) { setError(err.message); }
    finally { setApproving(null); }
  }

  async function reset() {
    if (!window.confirm("Reset the working database to its original HW5 state?")) return;
    try { await request("/api/reset", { method: "POST" }); await refresh(selectedId); setNotice("Working database reset. Original course data was not changed."); }
    catch (err) { setError(err.message); }
  }

  if (loading) return <div className="loading-screen">Loading the operations desk…</div>;
  return <div className="app-shell">
    <header className="topbar"><div><div className="eyebrow">CAMPUS CUSTOMS · MULTI-AGENT OPS</div><h1>Make the next move<br /><em>evidence-first.</em></h1><p>Tickets, specialist decisions, MCP evidence, and human-controlled payments in one readable desk.</p></div><div className="cash-card"><span>CHECKING BALANCE</span><strong>${Number(cash?.checking?.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong><small>{cash?.checking?.date || "—"} · live from API</small></div></header>
    <main className="layout"><aside className="sidebar"><div className="side-title">Open desk</div>{tickets.map((ticket) => <button key={ticket.id} className={`ticket-tab ${selected?.id === ticket.id ? "active" : ""}`} onClick={() => selectTicket(ticket.id)}><span>#{ticket.id}</span><strong>{ticket.subject}</strong><small>{ticket.type.replaceAll("_", " ")}</small><Status value={ticket.status} /></button>)}<button className="reset-button" onClick={reset}>Reset working database</button></aside>
      <section className="content">{error && <div className="alert error">{error}</div>}{notice && <div className="alert notice">{notice}</div>}{selected && <><div className="content-head"><div><div className="eyebrow">TICKET {selected.id} · {selected.requester}</div><h2>{selected.subject}</h2><p>{selected.notes}</p></div><div className="head-actions"><Status value={selected.status} /><button className="run-button" disabled={running} onClick={runTicket}>{running ? "Running…" : "Run Boss workflow"}</button></div></div><div className="fact-grid"><div><span>Type</span><strong>{selected.type.replaceAll("_", " ")}</strong></div><div><span>Created</span><strong>{selected.created_at}</strong></div><div><span>SKU</span><strong>{selected.sku || "No SKU"}</strong></div><div><span>Request</span><strong>{selected.qty ? `${selected.qty} × ${selected.size}` : selected.lease_id ? `Lease #${selected.lease_id}` : selected.invoice_id ? `Invoice #${selected.invoice_id}` : "Review"}</strong></div></div><div className="panel"><div className="panel-head"><div><div className="eyebrow">ACTIVITY STREAM</div><h3>What the team did</h3></div><span>{events.length} events</span></div>{events.length ? <div className="events">{events.map((event) => <EventRow key={event.id} event={event} />)}</div> : <div className="empty">No run evidence yet. Start the Boss workflow to see delegations, MCP calls, and decisions here.</div>}</div><div className="two-col"><div className="panel"><div className="eyebrow">PAYMENT CONTROL</div><h3>Human approval queue</h3>{requests.filter((item) => item.ticket_id === selected.id).length ? requests.filter((item) => item.ticket_id === selected.id).map((item) => <div className="payment-card" key={item.id}><div><strong>${Number(item.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong><span>{item.kind} · {item.status}</span><p>{item.reason}</p></div>{item.status === "pending" ? <button className="approve" disabled={approving === item.id} onClick={() => approve(item.id)}>{approving === item.id ? "Approving…" : "Approve payment"}</button> : <Status value={item.status} />}</div>) : <div className="empty">No payment request for this ticket.</div>}</div><div className="panel"><div className="eyebrow">DATABASE SNAPSHOT</div><h3>Ticket facts</h3><dl>{Object.entries(ticketDetail?.ticket || selected).filter(([key]) => !["notes"].includes(key)).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value ?? "—")}</dd></div>)}</dl></div></div></>}</section>
    </main><footer>Powered by FastAPI · PydanticAI · FastMCP · Portkey <span>·</span> No payment executes without explicit approval.</footer>
  </div>;
}

export default App;

