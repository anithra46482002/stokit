import React from "react";
import api from "./api";
import { errorText } from "./uiUtils";
const money = v => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 }).format(Number(v) || 0);
export default function ManageAllocationsPage({ canWrite = false }) {
  const [rows, setRows] = React.useState([]), [offers, setOffers] = React.useState([]);
  const [offerId, setOfferId] = React.useState(""), [user, setUser] = React.useState(""), [month, setMonth] = React.useState("");
  const [applied, setApplied] = React.useState({}), [businessMonth, setBusinessMonth] = React.useState(""), [reportMonth, setReportMonth] = React.useState(""), [page, setPage] = React.useState(1), [count, setCount] = React.useState(0);
  const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(""), [notice, setNotice] = React.useState("");
  const [form, setForm] = React.useState(null);
  const load = React.useCallback(async () => {
    setBusy(true); setError("");
    try {
      const [a, o] = await Promise.all([
        api.get("allocations", { params: { page, page_size: 20, ...applied } }),
        api.get("advance-payments", { params: { page_size: 100 } })
      ]);
      setRows(a.data.results || []); setCount(Number(a.data.count || 0)); setOffers(o.data.results || []);
      setBusinessMonth(String(a.data.as_of_date || "").slice(0, 7)); setReportMonth(String(a.data.month || ""));
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }, [page, applied]);
  // oxlint-disable-next-line react/set-state-in-effect -- intentional API-loading effect. 
  React.useEffect(() => { load(); }, [load]);
  const apply = () => {
    const chosen = month || businessMonth;
    if (chosen && !/^\d{4}-(0[1-9]|1[0-2])$/.test(chosen)) { setError("Choose a valid reporting month before filtering."); return; }
    setError(""); setPage(1); setApplied({ ...(chosen ? { month: chosen } : {}), ...(offerId ? { offer_id: offerId } : {}), ...(user.trim() ? { user: user.trim() } : {}) });
  };
  const reset = () => { setOfferId(""); setUser(""); setMonth(""); setPage(1); setApplied({}); };
  function edit(r) { setForm({ mode: "edit", id: r.id, status: r.status, payment_date: r.payment_date, start_date: r.start_date, end_date: r.end_date, payment_reference: r.payment_reference || "", notes: r.notes || "" }); }
  async function save(event) {
    event.preventDefault(); if (busy || !form) return;
    setBusy(true); setError(""); setNotice("");
    const payload = { status: form.status, payment_reference: form.payment_reference, notes: form.notes };
    try {
      await api.patch(`allocations/${form.id}`, payload);
      setForm(null); setNotice("Allocation updated."); await load();
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function remove(r) {
    if (!window.confirm(`Cancel allocation #${r.id}? Transaction history will be preserved.`)) return;
    setBusy(true); setError("");
    try { await api.delete(`allocations/${r.id}`); setNotice(`Allocation #${r.id} cancelled; history preserved.`); await load(); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const periodLabel = !reportMonth || reportMonth === businessMonth ? "Current Month" : reportMonth;
  const columns = ["ID", "Offer", "User", "Payment Amount", "Bonus Percentage", "Duration Months", "Total Credit", "Monthly Credit Release", "Bonus per Month", "Carried Forward — " + periodLabel, "Used Credit — " + periodLabel, "Remaining Credit — " + periodLabel, "Lifetime Used Credit (all months)", "Start Date", "End Date", "Status", "Actions"];
  return <section className="resource-page allocation-page">
    <div className="page-heading"><div><h2>Allocation Management</h2><p>Review offer allocations and each month's credit release and usage.</p></div><div><button onClick={load} disabled={busy}>Refresh</button></div></div>
    <div className="allocation-summary"><div className="toolbar allocation-filters">
      <label>Offer<select value={offerId} onChange={e => setOfferId(e.target.value)}><option value="">All offers</option>{offers.map(o => <option key={o.id} value={o.id}>{o.offer_name}</option>)}</select></label>
      <label>User search<input value={user} onChange={e => setUser(e.target.value)} placeholder="Username or customer name" /></label>
      <label>Reporting month<input type="month" value={month || businessMonth} onChange={e => setMonth(e.target.value)} /></label>
      <button className="primary-action" onClick={apply} disabled={busy}>Filter</button><button onClick={reset} disabled={busy}>Reset</button>
    </div></div>
    {reportMonth && <p className="allocation-note">Reporting month: <strong>{reportMonth}</strong> (business timezone). Monthly credit = payment × bonus % ÷ 100. Remaining credit = this month’s credit + unused credit carried forward from earlier months − this month’s usage. Lifetime usage is shown separately and is not spendable credit.</p>}
    {error && <p className="error" role="alert">{error}</p>}{notice && <p className="success" role="status">{notice}</p>}{busy && <p className="empty" role="status">Loading allocation records…</p>}
    <div className="table-wrap allocation-table-wrap"><table className="allocation-table"><thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>
      {rows.map(r => <tr key={r.id}><td>{r.id}</td><td>{r.offer_name}</td><td>{r.full_name || r.username || `User #${r.user_id}`}</td><td>{money(r.payment_amount)}</td><td>{r.bonus_percentage}%</td><td>{r.duration_months}</td><td>{money(r.total_credit)}</td><td>{money(r.monthly_credit_release)}</td><td>{money(r.monthly_bonus ?? r.monthly_credit_release)}</td><td>{money(r.carry_forward)}</td><td>{money(r.used_this_month)}</td><td>{money(r.remaining_this_month)}</td><td>{money(r.lifetime_used_credit)}</td><td>{r.start_date}</td><td>{r.end_date}</td><td><span className={`allocation-status status-${String(r.status).toLowerCase()}`}>{r.status}</span></td><td>{canWrite && <div className="row-actions"><button disabled={busy} onClick={() => edit(r)}>Edit</button><button className="danger-action" disabled={busy || r.status === "CANCELLED"} onClick={() => remove(r)}>Delete</button></div>}</td></tr>)}
    </tbody></table>{!busy && rows.length === 0 && <p className="empty">No allocations match these filters.</p>}</div>
    <div className="pagination"><span>{count} allocation(s) · Page {page}</span><button disabled={busy || page <= 1} onClick={() => setPage(p => p - 1)}>Previous</button><button disabled={busy || page * 20 >= count} onClick={() => setPage(p => p + 1)}>Next</button></div>
    {form && <div className="modal-backdrop"><section className="editor-dialog" role="dialog" aria-modal="true" aria-labelledby="allocation-editor-title">
      <h2 id="allocation-editor-title">Edit allocation #{form.id}</h2>
      <form onSubmit={save}><div className="form-grid">

        {form.mode === "edit" && <label>Status<select value={form.status} onChange={e => setForm(v => ({ ...v, status: e.target.value }))}><option>ACTIVE</option><option>COMPLETED</option><option>CANCELLED</option></select></label>}
        <label>Payment date *<input type="date" required disabled={form.mode === "edit"} value={form.payment_date} onChange={e => setForm(v => ({ ...v, payment_date: e.target.value }))} /></label>
        <label>Start date *<input type="date" required disabled={form.mode === "edit"} value={form.start_date} onChange={e => setForm(v => ({ ...v, start_date: e.target.value }))} /></label>
        <label>End date *<input type="date" required disabled={form.mode === "edit"} value={form.end_date} onChange={e => setForm(v => ({ ...v, end_date: e.target.value }))} /></label>
        <label>Payment reference<input maxLength={255} value={form.payment_reference} onChange={e => setForm(v => ({ ...v, payment_reference: e.target.value }))} /></label>
        <label className="wide">Notes<textarea value={form.notes} onChange={e => setForm(v => ({ ...v, notes: e.target.value }))} /></label>
      </div><p>Offer, user and credit amounts are protected to preserve transaction history.</p><div className="button-row"><button type="button" disabled={busy} onClick={() => setForm(null)}>Cancel</button><button type="submit" className="primary-action" disabled={busy}>{busy ? "Saving…" : "Save allocation"}</button></div></form>
    </section></div>}
  </section>;
}
