import React from 'react';
import { Users, UserPlus, Crown, Tag, Palette, Warehouse, Eye, Pencil, Trash2, User, X } from 'lucide-react';
import api, { uploadImage } from './api';
import { errorText } from './uiUtils';
import { validateEmail, validateGstNumber, validateMobile } from './fieldValidation';

const PAGE_SIZE = 20;
const SALESMAN_FIELDS = ['full_name', 'shop_name', 'email', 'phone', 'address', 'city'];
const EMPTY_FILTERS = { vip: '', offer_id: '', color: '', warehouse_id: '' };
const BLANK_FORM = {
  username: '', password: '', full_name: '', shop_name: '', category_id: '', email: '', phone: '', address: '', city: '',
  profile_picture: '', color_code: '', status: 'ACTIVE', gst: 'N', gst_type: '', gst_number: '', gst_percentage: '', vip_discount: 'N', vip_percentage: '0',
  delivery_charges: '0', store_maped: 'N', warehouse_id: '',
};

function toForm(row) {
  const form = { ...BLANK_FORM };
  Object.keys(BLANK_FORM).forEach((key) => {
    if (key === 'password' || key === 'username') return;
    const value = row[key];
    form[key] = value == null ? '' : String(value);
  });
  form.username = row.username;
  return form;
}

function Flag({ value, vip }) {
  const v = String(value || '').toUpperCase();
  if (!v) return <span className="cus-flag cus-flag-empty" aria-label="not set" />;
  return <span className={'cus-flag' + (vip && v === 'Y' ? ' cus-flag-vip' : v === 'Y' ? ' cus-flag-yes' : '')}>{v}</span>;
}

function Avatar({ url, name }) {
  const [failed, setFailed] = React.useState(false);
  if (url && !failed) return <img className="cus-avatar" src={url} alt={'Profile of ' + name} loading="lazy" onError={() => setFailed(true)} />;
  return <span className="cus-avatar cus-avatar-empty" aria-hidden="true"><User size={20} /></span>;
}

function Field({ label, required, children, help, error }) {
  return <label><span>{label}{required && <b className="sk-req"> *</b>}</span>{children}{help && <small>{help}</small>}{error && <small className="error" role="alert">{error}</small>}</label>;
}

function DetailRow({ label, value }) {
  return <><dt>{label}</dt><dd>{value === null || value === undefined || value === '' ? '\u2014' : String(value)}</dd></>;
}

export default function CustomersPage({ role }) {
  const isAdmin = role === 'SUPER_ADMIN' || role === 'ADMIN';
  const canEdit = isAdmin || role === 'SALESMAN';
  const [data, setData] = React.useState(null);
  const [filters, setFilters] = React.useState(EMPTY_FILTERS);
  const [search, setSearch] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [dialog, setDialog] = React.useState(null); // {mode:'add'|'edit'|'view', row?}
  const [form, setForm] = React.useState(BLANK_FORM);
  const [formError, setFormError] = React.useState('');
  const [fieldErrors, setFieldErrors] = React.useState({});
  const [showPassword, setShowPassword] = React.useState(false);
  const [file, setFile] = React.useState(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (search.trim()) params.search = search.trim();
      Object.entries(filters).forEach(([key, value]) => { if (value) params[key] = value; });
      const response = await api.get('customers', { params });
      setData(response.data);
      setError('');
    } catch (err) {
      setData(null);
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [page, search, filters]);
  // oxlint-disable-next-line react/set-state-in-effect
  React.useEffect(() => { load(); }, [load]);

  const rows = data?.results || [];
  const options = data?.filters || { colors: [], warehouses: [], offers: [] };
  const categories = data?.shop_categories || [];
  const pages = Math.max(1, Math.ceil((data?.count || 0) / PAGE_SIZE));
  const filtered = Boolean(search.trim() || Object.values(filters).some(Boolean));

  function setFilter(key, value) { setPage(1); setFilters((previous) => ({ ...previous, [key]: value })); }
  function resetFilters() { setPage(1); setSearch(''); setFilters(EMPTY_FILTERS); }

  function openAdd() { setForm(BLANK_FORM); setFile(null); setFormError(''); setFieldErrors({}); setNotice(''); setDialog({ mode: 'add' }); }
  function openEdit(row) { setForm(toForm(row)); setFile(null); setFormError(''); setFieldErrors({}); setNotice(''); setDialog({ mode: 'edit', row }); }
  function closeDialog() { if (!busy) setDialog(null); }
  function setField(key, value) { setForm((previous) => ({ ...previous, [key]: value })); }

  function validate(values, mode) {
    if (mode === 'add') {
      if (!/^[A-Za-z0-9_.@-]{3,100}$/.test(values.username || '')) return 'Username must be 3-100 letters, digits or . _ @ - characters.';
      if ((values.password || '').length < 10) return 'Password must be at least 10 characters.';
    }
    if (!String(values.full_name || '').trim()) return 'Customer name is required.';
    const emailError = validateEmail(values.email, { required: true });
    if (emailError) return emailError;
    const phoneError = validateMobile(values.phone, { required: false });
    if (phoneError) return phoneError;
    const gstNumberError = validateGstNumber(values.gst_number);
    if (gstNumberError) return gstNumberError;
    if (values.gst_percentage !== "" && (!Number.isFinite(Number(values.gst_percentage)) || Number(values.gst_percentage) < 0 || Number(values.gst_percentage) > 100)) return "GST percentage must be between 0 and 100.";
    if (values.vip_percentage !== '' && (Number(values.vip_percentage) < 0 || Number(values.vip_percentage) > 100 || Number.isNaN(Number(values.vip_percentage)))) return 'VIP percentage must be between 0 and 100.';
    if (values.delivery_charges !== '' && (Number(values.delivery_charges) < 0 || Number.isNaN(Number(values.delivery_charges)))) return 'Delivery charges cannot be negative.';
    return '';
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const mode = dialog.mode;
    setFormError('');
    setFieldErrors({});
    const problem = validate(form, mode);
    if (problem) {
      const errors = {};
      if (/GST Number/i.test(problem)) errors.gst_number = problem;
      if (/GST percentage/i.test(problem)) errors.gst_percentage = problem;
      setFieldErrors(errors);
      setFormError(problem);
      return;
    }
    setBusy(true);
    try {
      const values = { ...form };
      if (file) values.profile_picture = (await uploadImage(file)).image_path;
      if (mode === 'add') {
        const payload = { ...values };
        Object.keys(payload).forEach((k) => { if (payload[k] === '') delete payload[k]; });
        await api.post('customers', payload);
        setNotice('Customer created.');
      } else {
        const original = toForm(dialog.row);
        const allowed = role === 'SALESMAN' ? SALESMAN_FIELDS : Object.keys(BLANK_FORM).filter((k) => k !== 'username' && k !== 'password');
        const changes = {};
        allowed.forEach((key) => { if (values[key] !== original[key]) changes[key] = values[key]; });
        if (Object.keys(changes).length === 0) { setFormError('No changes to save.'); setBusy(false); return; }
        await api.patch('customers', { id: dialog.row.id, ...changes });
        setNotice('Customer updated.');
      }
      setDialog(null);
      await load();
    } catch (err) {
      const apiErrors = err.response?.data?.errors || {};
      setFieldErrors(Object.fromEntries(Object.entries(apiErrors).filter(([key]) => ['gst_number', 'gst_percentage'].includes(key))));
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(row) {
    if (busy) return;
    if (!window.confirm('Delete customer "' + row.username + '" (ID ' + row.id + ')? Customers with linked history will be deactivated to preserve records.')) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await api.delete('customers', { params: { id: row.id } });
      if (response.data?.action === 'deactivated') {
        setNotice('Customer has linked records, so the account was deactivated to preserve history and removed from this list.');
      } else {
        setNotice('Customer deleted successfully.');
      }
      if (rows.length === 1 && page > 1) {
        setPage(page - 1);
      } else {
        setData((previous) => previous ? {
          ...previous,
          count: Math.max(0, Number(previous.count || 0) - 1),
          results: (previous.results || []).filter((customer) => customer.id !== row.id),
        } : previous);
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const preview = file ? URL.createObjectURL(file) : (dialog?.row?.profile_url || '');

  return (
    <div className="sk-page cus-page">
      <div className="ord-head">
        <div>
          <span className="ord-eyebrow">Admin workspace</span>
          <h1><Users size={34} /> Customers</h1>
        </div>
        <div className="cus-head-right">
          <span className="cus-count"><User size={16} /> {data?.count ?? 0} customers</span>
          {isAdmin && <button type="button" className="sk-btn-primary" onClick={openAdd}><UserPlus size={18} /> Add Customer</button>}
        </div>
      </div>

      <div className="sk-card ord-filters cus-filters">
        <label><span><Crown size={16} className="cus-crown" /> VIP:</span>
          <select value={filters.vip} onChange={(e) => setFilter('vip', e.target.value)}>
            <option value="">All</option><option value="Y">VIP only</option><option value="N">Non-VIP</option>
          </select></label>
        <label><span><Tag size={16} /> Offer Assigned:</span>
          <select value={filters.offer_id} onChange={(e) => setFilter('offer_id', e.target.value)}>
            <option value="">-- All Offers --</option>
            {options.offers.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select></label>
        <label><span><Palette size={16} /> Color:</span>
          <select value={filters.color} onChange={(e) => setFilter('color', e.target.value)}>
            <option value="">All Colors</option>
            {options.colors.map((c) => <option key={c} value={c}>{c}</option>)}
          </select></label>
        <label><span><Warehouse size={16} /> Warehouse:</span>
          <select value={filters.warehouse_id} onChange={(e) => setFilter('warehouse_id', e.target.value)}>
            <option value="">-- All Warehouses --</option>
            {options.warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select></label>
        <label className="cus-search"><span className="sr-only">Search customers</span>
          <input type="search" placeholder="Search name, email, phone..." value={search} onChange={(e) => { setPage(1); setSearch(e.target.value); }} /></label>
        {filtered && <button type="button" onClick={resetFilters}><X size={16} /> Reset</button>}
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}

      <section className="sk-card sk-flush">
        {loading && <p className="empty" role="status">Loading customers...</p>}
        {!loading && !error && rows.length === 0 && <p className="empty">{filtered ? 'No customers match these filters.' : 'No customers yet.'}</p>}
        {rows.length > 0 && (
          <div className="table-wrap">
            <table className="sk-table sk-upper-head cus-table">
              <thead><tr><th>#</th><th>Profile</th><th>Customer</th><th>Shop</th><th>Email</th><th>Phone</th><th>Status</th><th>GST</th><th>VIP</th><th>Store</th><th>Warehouse</th><th>Actions</th></tr></thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={row.id}>
                    <td className="sk-muted">{(page - 1) * PAGE_SIZE + index + 1}</td>
                    <td><Avatar url={row.profile_url} name={row.username} /></td>
                    <td><div className="cus-name"><span className="cus-dot" style={{ background: row.color_code || '#c8c8c8' }} title={row.color_code || 'No colour'} />
                      <div><strong>{row.username}</strong><small>{row.full_name}</small></div></div></td>
                    <td>{row.shop_name || ''}</td>
                    <td>{row.email}</td>
                    <td>{row.phone || ''}</td>
                    <td><span className={'ord-pill ' + (row.status === 'ACTIVE' ? 'ord-pill-green' : row.status === 'SUSPENDED' ? 'ord-pill-red' : '')}>{row.status}</span></td>
                    <td><Flag value={row.gst} /></td>
                    <td><Flag value={row.vip_discount} vip /></td>
                    <td><Flag value={row.store_maped} /></td>
                    <td>{row.warehouse_name || '-'}</td>
                    <td><div className="cus-actions">
                      <button type="button" className="cus-btn cus-btn-view" onClick={(event) => { event.stopPropagation(); setDialog({ mode: 'view', row }); }} aria-label={'View ' + row.username}><Eye size={15} /></button>
                      {canEdit && <button type="button" className="cus-btn cus-btn-edit" onClick={(event) => { event.stopPropagation(); openEdit(row); }} disabled={busy} aria-label={'Edit ' + row.username}><Pencil size={15} /></button>}
                      {isAdmin && <button type="button" className="cus-btn cus-btn-del" onClick={(event) => { event.stopPropagation(); remove(row); }} disabled={busy} aria-label={'Delete ' + row.username}><Trash2 size={15} /></button>}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.count > 0 && (
          <div className="pagination">
            <span>{data.count} customers - Page {page} of {pages}</span>
            <div className="button-row">
              <button type="button" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</button>
              <button type="button" disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </div>
        )}
      </section>

      {dialog && dialog.mode === 'view' && (
        <div className="modal-backdrop"><section className="editor-dialog" role="dialog" aria-modal="true" aria-labelledby="cus-view-title">
          <div className="page-heading"><h2 id="cus-view-title">{dialog.row.username}</h2><button type="button" onClick={closeDialog}>Close</button></div>
          <div className="cus-view-top"><Avatar url={dialog.row.profile_url} name={dialog.row.username} /><div><strong>{dialog.row.full_name}</strong><p className="sk-muted">{dialog.row.shop_name || 'No shop name'}</p></div></div>
          <dl className="cus-dl">
            <DetailRow label="Email" value={dialog.row.email} /><DetailRow label="Phone" value={dialog.row.phone} />
            <DetailRow label="Address" value={dialog.row.address} /><DetailRow label="City" value={dialog.row.city} />
            <DetailRow label="Status" value={dialog.row.status} /><DetailRow label="Colour" value={dialog.row.color_code} />
            <DetailRow label="GST registered" value={dialog.row.gst} /><DetailRow label="GST type" value={dialog.row.gst_type} /><DetailRow label="GST Number" value={dialog.row.gst_number} /><DetailRow label="GST Percentage (%)" value={dialog.row.gst_percentage} />
            <DetailRow label="VIP discount" value={dialog.row.vip_discount === 'Y' ? 'Yes (' + dialog.row.vip_percentage + '%)' : 'No'} />
            <DetailRow label="Delivery charges" value={dialog.row.delivery_charges} />
            <DetailRow label="Store mapped" value={dialog.row.store_maped} /><DetailRow label="Warehouse" value={dialog.row.warehouse_name} />
          </dl>
        </section></div>
      )}

      {dialog && dialog.mode !== 'view' && (
        <div className="modal-backdrop"><section className="editor-dialog cus-dialog" role="dialog" aria-modal="true" aria-labelledby="cus-form-title">
          <div className="page-heading"><h2 id="cus-form-title">{dialog.mode === 'add' ? 'Add Customer' : 'Edit ' + dialog.row.username}</h2><button type="button" onClick={closeDialog} disabled={busy}>Close</button></div>
          {formError && <p className="error" role="alert">{formError}</p>}
          <form className="sk-form" onSubmit={submit} noValidate>
            <div className="sk-form-grid">
              {dialog.mode === 'add' && <Field label="Username" required help="Use 3â€“100 letters, numbers, or . _ @ - only. Spaces and other characters are removed automatically."><input value={form.username} onChange={(e) => setField('username', e.target.value.replace(/[^A-Za-z0-9_.@-]/g, '').slice(0, 100))} minLength={3} maxLength={100} autoComplete="off" autoCapitalize="none" spellCheck={false} /></Field>}
              {dialog.mode === 'add' && <Field label="Password" required help="At least 10 characters."><span className="cus-password-field"><input type={showPassword ? 'text' : 'password'} value={form.password} onChange={(e) => setField('password', e.target.value)} autoComplete="new-password" /><button type="button" className="cus-password-toggle" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? 'Hide' : 'Show'}</button></span></Field>}
              <Field label="Full name" required><input value={form.full_name} onChange={(e) => setField('full_name', e.target.value)} /></Field>
              <Field label="Shop name"><input value={form.shop_name} onChange={(e) => setField('shop_name', e.target.value)} /></Field>
              <Field label="Email" required><input type="email" autoComplete="email" maxLength={254} value={form.email} onChange={(e) => setField('email', e.target.value)} /></Field>
              <Field label="Phone"><input type="tel" inputMode="tel" autoComplete="tel" maxLength={20} value={form.phone} onChange={(e) => setField('phone', e.target.value)} /></Field>
              <Field label="City"><input value={form.city} onChange={(e) => setField('city', e.target.value)} /></Field>
              <Field label="Address"><input value={form.address} onChange={(e) => setField('address', e.target.value)} /></Field>
              {role !== 'SALESMAN' && <>
                <Field label="Shop category"><select value={form.category_id} onChange={(e) => setField('category_id', e.target.value)}>
                  <option value="">-- None --</option>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
                <Field label="Warehouse"><select value={form.warehouse_id} onChange={(e) => setField('warehouse_id', e.target.value)}>
                  <option value="">-- None --</option>{options.warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></Field>
                <Field label="Status"><select value={form.status} onChange={(e) => setField('status', e.target.value)}>
                  <option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option><option value="SUSPENDED">Suspended</option></select></Field>
                <Field label="Colour code" help="Hex colour, e.g. #33FF57. Leave empty for none."><span className="cus-color-row">
                  <input type="color" aria-label="Pick colour" value={/^#[0-9A-Fa-f]{6}$/.test(form.color_code) ? form.color_code : '#c8c8c8'} onChange={(e) => setField('color_code', e.target.value.toUpperCase())} />
                  <input value={form.color_code} onChange={(e) => setField('color_code', e.target.value)} placeholder="#RRGGBB" /></span></Field>
                <Field label="GST registered"><select value={form.gst} onChange={(e) => setField('gst', e.target.value)}><option value="N">No</option><option value="Y">Yes</option></select></Field>
                <Field label="GST Number" error={fieldErrors.gst_number} help="Optional. If entered, it must be exactly 15 characters."><input autoComplete="off" maxLength={15} value={form.gst_number} onChange={(e) => setField("gst_number", e.target.value)} /></Field>
                <Field label="GST Percentage (%)" error={fieldErrors.gst_percentage} help="Optional customer metadata; does not change product or cart GST."><input type="number" min="0" max="100" step="0.01" value={form.gst_percentage} onChange={(e) => setField("gst_percentage", e.target.value)} /></Field>
                <Field label="GST type"><select value={form.gst_type} onChange={(e) => setField('gst_type', e.target.value)}>
                  <option value="">-- None --</option><option value="REGULAR">Regular</option><option value="COMPOUND">Compound</option></select></Field>
                <Field label="VIP discount"><select value={form.vip_discount} onChange={(e) => setField('vip_discount', e.target.value)}><option value="N">No</option><option value="Y">Yes</option></select></Field>
                <Field label="VIP percentage"><input type="number" min="0" max="100" step="0.01" value={form.vip_percentage} onChange={(e) => setField('vip_percentage', e.target.value)} /></Field>
                <Field label="Delivery charges"><input type="number" min="0" step="0.01" value={form.delivery_charges} onChange={(e) => setField('delivery_charges', e.target.value)} /></Field>
                <Field label="Store mapped"><select value={form.store_maped} onChange={(e) => setField('store_maped', e.target.value)}><option value="N">No</option><option value="Y">Yes</option></select></Field>
                <Field label="Profile image" help="Optional. Leave empty to keep the current image."><span className="cus-upload">
                  {preview ? <img className="cus-avatar" src={preview} alt="Profile preview" /> : <span className="cus-avatar cus-avatar-empty"><User size={20} /></span>}
                  <input type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={(e) => setFile(e.target.files?.[0] || null)} /></span></Field>
              </>}
            </div>
            <div className="button-row">
              <button type="submit" className="sk-btn-primary" disabled={busy}>{busy ? 'Saving...' : dialog.mode === 'add' ? 'Create Customer' : 'Save Changes'}</button>
              <button type="button" onClick={closeDialog} disabled={busy}>Cancel</button>
            </div>
          </form>
        </section></div>
      )}
    </div>
  );
}
