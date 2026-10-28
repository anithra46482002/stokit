import React from 'react';
import { Bell, Mail, Plus, Eye, Trash2, User, Users, Send } from 'lucide-react';
import api from './api';
import { errorText, fetchAll } from './uiUtils';

const PAGE_SIZE = 20;

function formatSent(value) {
  if (!value) return '\u2014';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const date = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  return date + ', ' + time;
}

function Recipient({ row }) {
  if (row.recipient_type === 'all') return <span className="not-recipient"><Users size={14} /> All Customers</span>;
  return <span className="not-recipient"><User size={14} /> {row.customer_name || ('Customer #' + row.customer_id)}</span>;
}

const BLANK = { title: '', message: '', recipient_type: 'all', customer_id: '' };

export default function NotificationsPage({ canWrite }) {
  const [data, setData] = React.useState(null);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [viewRow, setViewRow] = React.useState(null);
  const [composing, setComposing] = React.useState(false);
  const [form, setForm] = React.useState(BLANK);
  const [formError, setFormError] = React.useState('');
  const [customers, setCustomers] = React.useState([]);
  const [customersError, setCustomersError] = React.useState('');

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('notifications', { params: { page, page_size: PAGE_SIZE } });
      setData(response.data);
      setError('');
    } catch (err) {
      setData(null);
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [page]);
  // oxlint-disable-next-line react/set-state-in-effect
  React.useEffect(() => { load(); }, [load]);

  async function openCompose() {
    setForm(BLANK); setFormError(''); setNotice(''); setComposing(true); setCustomersError('');
    try {
      setCustomers(await fetchAll(api, 'customers'));
    } catch (err) {
      setCustomers([]);
      setCustomersError('Could not load customers: ' + errorText(err));
    }
  }

  async function send(event) {
    event.preventDefault();
    if (busy) return;
    setFormError('');
    if (!form.title.trim()) { setFormError('Title is required.'); return; }
    if (!form.message.trim()) { setFormError('Message is required.'); return; }
    if (form.recipient_type === 'selected' && !form.customer_id) { setFormError('Choose the customer who should receive this message.'); return; }
    setBusy(true);
    try {
      const payload = { title: form.title.trim(), message: form.message.trim(), recipient_type: form.recipient_type };
      if (form.recipient_type === 'selected') payload.customer_id = Number(form.customer_id);
      const response = await api.post('notifications', payload);
      setComposing(false);
      setNotice(response.data?.delivery_note || 'Notification saved.');
      setPage(1);
      await load();
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    if (busy) return;
    if (!window.confirm('Delete notification "' + row.title + '"? This cannot be undone.')) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await api.delete('notifications', { params: { id: row.id } });
      setNotice('Notification deleted.');
      if (rows.length === 1 && page > 1) setPage(page - 1); else await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const rows = data?.results || [];
  const pages = Math.max(1, Math.ceil((data?.count || 0) / PAGE_SIZE));

  return (
    <div className="sk-page not-page">
      <div className="ord-head">
        <div>
          <span className="ord-eyebrow">Admin workspace</span>
          <h1><Bell size={34} /> Notifications</h1>
        </div>
        <div className="cus-head-right">
          <span className="cus-count"><Mail size={16} /> {data?.count ?? 0} sent</span>
          {canWrite && <button type="button" className="sk-btn-primary" onClick={openCompose}><Plus size={18} /> New Message</button>}
        </div>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}

      <section className="sk-card sk-flush">
        {loading && <p className="empty" role="status">Loading notifications...</p>}
        {!loading && !error && rows.length === 0 && <p className="empty">No notifications have been sent yet.</p>}
        {rows.length > 0 && (
          <div className="table-wrap">
            <table className="sk-table sk-upper-head">
              <thead><tr><th>#</th><th>Title</th><th>Message</th><th>Recipient</th><th>Type</th><th>Status</th><th>Sent By</th><th>Sent At</th><th>Actions</th></tr></thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={row.id}>
                    <td className="sk-muted">{(page - 1) * PAGE_SIZE + index + 1}</td>
                    <td><strong>{row.title}</strong></td>
                    <td className="not-msg">{row.message}</td>
                    <td><Recipient row={row} /></td>
                    <td><span className={'ord-pill ' + (row.recipient_type === 'all' ? 'ord-pill-blue' : 'ord-pill-amber')}>{String(row.recipient_type).toUpperCase()}</span></td>
                    <td><span className={'ord-pill ' + (row.is_read ? 'ord-pill-green' : 'ord-pill-red')}>{row.is_read ? 'READ' : 'UNREAD'}</span></td>
                    <td>{row.sent_by || '\u2014'}</td>
                    <td>{formatSent(row.created_at)}</td>
                    <td><div className="not-actions">
                      <button type="button" className="not-btn not-btn-view" onClick={() => setViewRow(row)}><Eye size={14} /> View</button>
                      {canWrite && <button type="button" className="not-btn not-btn-del" onClick={() => remove(row)} disabled={busy}><Trash2 size={14} /> Delete</button>}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.count > 0 && (
          <div className="pagination">
            <span>{data.count} notifications - Page {page} of {pages}</span>
            <div className="button-row">
              <button type="button" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button>
              <button type="button" disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </div>
        )}
      </section>

      {viewRow && (
        <div className="modal-backdrop"><section className="editor-dialog" role="dialog" aria-modal="true" aria-labelledby="not-view-title">
          <div className="page-heading"><h2 id="not-view-title">{viewRow.title}</h2><button type="button" onClick={() => setViewRow(null)}>Close</button></div>
          <p className="not-full">{viewRow.message}</p>
          <dl className="cus-dl">
            <dt>Recipient</dt><dd><Recipient row={viewRow} /></dd>
            <dt>Type</dt><dd>{String(viewRow.recipient_type).toUpperCase()}</dd>
            <dt>Status</dt><dd>{viewRow.is_read ? 'Read' + (viewRow.read_at ? ' on ' + formatSent(viewRow.read_at) : '') : 'Unread'}</dd>
            <dt>Sent by</dt><dd>{viewRow.sent_by || '\u2014'}</dd>
            <dt>Sent at</dt><dd>{formatSent(viewRow.created_at)}</dd>
          </dl>
        </section></div>
      )}

      {composing && (
        <div className="modal-backdrop"><section className="editor-dialog" role="dialog" aria-modal="true" aria-labelledby="not-new-title">
          <div className="page-heading"><h2 id="not-new-title">New Message</h2><button type="button" onClick={() => !busy && setComposing(false)} disabled={busy}>Close</button></div>
          {formError && <p className="error" role="alert">{formError}</p>}
          {customersError && <p className="error" role="alert">{customersError}</p>}
          <form className="sk-form" onSubmit={send} noValidate>
            <label><span>Title <b className="sk-req">*</b></span><input maxLength={255} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
            <label><span>Message <b className="sk-req">*</b></span><textarea rows="4" maxLength={5000} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} /></label>
            <label><span>Send to</span>
              <select value={form.recipient_type} onChange={(e) => setForm({ ...form, recipient_type: e.target.value, customer_id: '' })}>
                <option value="all">All customers</option><option value="selected">Selected customer</option>
              </select></label>
            {form.recipient_type === 'selected' && (
              <label><span>Customer <b className="sk-req">*</b></span>
                <select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
                  <option value="">-- Select customer --</option>
                  {customers.map((c) => <option key={c.id} value={c.id}>{c.username}{c.full_name ? ' - ' + c.full_name : ''}</option>)}
                </select></label>
            )}
            {form.recipient_type === 'all' && <p className="sk-warn">This message will be visible to every customer.</p>}
            <div className="button-row">
              <button type="submit" className="sk-btn-primary" disabled={busy}><Send size={16} /> {busy ? 'Sending...' : 'Send Message'}</button>
              <button type="button" onClick={() => setComposing(false)} disabled={busy}>Cancel</button>
            </div>
          </form>
        </section></div>
      )}
    </div>
  );
}
