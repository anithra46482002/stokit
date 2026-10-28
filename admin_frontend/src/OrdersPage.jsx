import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShoppingCart, RefreshCw, Search, X, UserCheck, Eye, Pencil, Trash2, List, Calendar, Filter, Palette, Warehouse, IndianRupee, Clock, ArrowLeft, Home as HomeIcon } from 'lucide-react';
import api from './api';
import { errorText, fetchAll } from './uiUtils';
import { money, formatDateTime, statusClass, validateOrderLines } from './orderUtils';

const EMPTY_FILTERS = { from_date: '', to_date: '', status: 'all', color_code: '', warehouse_id: '', delivery_boy_id: '' };

function cleanParams(filters) {
  const params = {};
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== '' && value != null && !(key === 'status' && value === 'all')) params[key] = value;
  });
  return params;
}

export default function OrdersPage({ canAssign }) {
  const navigate = useNavigate();
  const [draft, setDraft] = React.useState(EMPTY_FILTERS);
  const [applied, setApplied] = React.useState(EMPTY_FILTERS);
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [selected, setSelected] = React.useState([]);
  const [boyId, setBoyId] = React.useState('');
  const [assigning, setAssigning] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [createBusy, setCreateBusy] = React.useState(false);
  const [products, setProducts] = React.useState([]);
  const [createForm, setCreateForm] = React.useState({ full_name: '', email: '', phone: '', address: '', city: '', state: '', postal_code: '', country: 'India', payment_method: 'COD' });
  const [createItems, setCreateItems] = React.useState([{ product_id: '', variant_id: '', quantity: 1 }]);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('orders/manage', { params: cleanParams(applied) });
      setData(response.data);
      setError('');
      setSelected([]);
    } catch (err) {
      setData(null);
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [applied]);
  // oxlint-disable-next-line react/set-state-in-effect
  React.useEffect(() => { load(); }, [load]);

  React.useEffect(() => {
    if (!createOpen || products.length) return;
    let active = true;
    fetchAll(api, 'products').then((rows) => { if (active) setProducts(rows); }).catch((err) => { if (active) setError(errorText(err)); });
    return () => { active = false; };
  }, [createOpen, products.length]);

  function setCreateField(field, value) {
    setCreateForm((previous) => ({ ...previous, [field]: value }));
  }

  function setCreateItem(index, field, value) {
    setCreateItems((previous) => previous.map((item, i) => i === index ? { ...item, [field]: value } : item));
  }

  function setCreateProduct(index, productId) {
    setCreateItems((previous) => previous.map((item, i) => i === index ? { ...item, product_id: productId, variant_id: '' } : item));
  }

  const estimatedTotal = createItems.reduce((sum, item) => {
    const product = products.find((row) => String(row.id) === String(item.product_id));
    const variant = product?.variants?.find((row) => String(row.id) === String(item.variant_id));
    const price = item.variant_id ? Number(variant?.price || 0) : Number(product?.price || 0);
    const quantity = Number(item.quantity);
    return sum + (product && Number.isFinite(quantity) && quantity > 0 ? price * quantity : 0);
  }, 0);

  async function createOrder(event) {
    event.preventDefault();
    if (createBusy) return;
    const validationError = validateOrderLines(createItems, products);
    if (validationError) { setError(validationError); return; }
    setCreateBusy(true); setError(''); setNotice('');
    try {
      const response = await api.post('orders', { ...createForm, items: createItems.map((item) => ({ product_id: Number(item.product_id), variant_id: item.variant_id ? Number(item.variant_id) : null, quantity: Number(item.quantity) })) });
      setNotice(response.data?.message || 'Order created.');
      setCreateOpen(false);
      setCreateForm({ full_name: '', email: '', phone: '', address: '', city: '', state: '', postal_code: '', country: 'India', payment_method: 'COD' });
      setCreateItems([{ product_id: '', variant_id: '', quantity: 1 }]);
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setCreateBusy(false);
    }
  }

  const orders = data?.orders || [];
  const boys = data?.delivery_boys || [];
  const filters = data?.filters || {};
  const allSelected = orders.length > 0 && selected.length === orders.length;

  function set(field, value) { setDraft((previous) => ({ ...previous, [field]: value })); }

  function apply(event) {
    event.preventDefault();
    if (draft.from_date && draft.to_date && draft.from_date > draft.to_date) {
      setError('The From date cannot be after the To date.');
      return;
    }
    setNotice('');
    setApplied({ ...draft });
  }

  function reset() {
    setDraft(EMPTY_FILTERS);
    setNotice('');
    setApplied(EMPTY_FILTERS);
  }

  function toggle(id) {
    setSelected((previous) => (previous.includes(id) ? previous.filter((x) => x !== id) : [...previous, id]));
  }

  async function assign() {
    if (assigning) return;
    if (selected.length === 0) { setError('Select at least one order first.'); return; }
    if (!boyId) { setError('Choose a delivery boy first.'); return; }
    setAssigning(true); setError(''); setNotice('');
    try {
      const response = await api.post('orders/bulk-assign', { order_ids: selected, delivery_boy_id: Number(boyId) });
      setNotice(response.data?.message || 'Delivery boy assigned.');
      setBoyId('');
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setAssigning(false);
    }
  }

  async function deleteOrder(order) {
    if (!canAssign || assigning) return;
    if (!window.confirm('Permanently delete order #' + order.id + ' and its items and status history? This cannot be undone.')) return;
    setAssigning(true); setError(''); setNotice('');
    try {
      await api.delete('orders/' + order.id + '/detail');
      setNotice('Order #' + order.id + ' deleted.');
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setAssigning(false);
    }
  }

  const stats = data?.stats || { total_orders: 0, revenue: '0.00', pending_orders: 0 };
  const ranged = Boolean(data?.ranged);
  const labelOrders = ranged ? 'Orders in range' : 'Today\u2019s Orders';
  const labelRevenue = ranged ? 'Revenue in range' : 'Today\u2019s Revenue';
  const labelPending = ranged ? 'Pending in range' : 'Pending Today';

  return (
    <div className="sk-page ord-page">
      <div className="ord-reference-topbar"><button type="button" aria-label="Back to dashboard" onClick={() => navigate('/')}><ArrowLeft size={18} /></button><strong>Order Management</strong><button type="button" className="ord-home" onClick={() => navigate('/')}><HomeIcon size={16} /> Home</button></div>
      <div className="ord-head">
        <div>
          <span className="ord-eyebrow">Admin workspace</span>
          <h1><ShoppingCart size={34} /> Order Management</h1>
        </div>
        <div className="button-row">{canAssign && <button type="button" className="sk-btn-primary" onClick={() => setCreateOpen((open) => !open)} disabled={createBusy}><ShoppingCart size={18} /> {createOpen ? "Close New Order" : "Create Order"}</button>}<button type="button" className="sk-btn-primary" onClick={load} disabled={loading}><RefreshCw size={18} /> Refresh</button></div>
      </div>

      {createOpen && canAssign && <form className="sk-card sk-form" onSubmit={createOrder}>
        <h2>Create Order</h2>
        <p className="sk-muted">Prices are re-read and totals are calculated by the server. Delivery coordinates are not stored by the current checkout schema; enter the full address and locality below.</p>
        <div className="sk-form-grid">
          {[["full_name", "Customer name"], ["email", "Email"], ["phone", "Phone"], ["address", "Delivery address"], ["city", "City / place"], ["state", "State"], ["postal_code", "Postal code"], ["country", "Country"], ["payment_method", "Payment method"]].map(([field, label]) => <label key={field}><span>{label}</span><input required={["full_name", "email", "phone", "address"].includes(field)} type={field === "email" ? "email" : "text"} value={createForm[field]} onChange={(e) => setCreateField(field, e.target.value)} /></label>)}
        </div>
        <h3>Products</h3>
        {createItems.map((item, index) => <div className="sk-form-grid" key={index}>
          <label><span>Product</span><select required value={item.product_id} onChange={(e) => setCreateProduct(index, e.target.value)}><option value="">Choose product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} — ₹{product.price}</option>)}</select></label>{products.find((product) => String(product.id) === String(item.product_id))?.variants?.length > 0 && <label><span>Variant</span><select required value={item.variant_id || ""} onChange={(e) => setCreateItem(index, "variant_id", e.target.value)}><option value="">Choose variant</option>{products.find((product) => String(product.id) === String(item.product_id)).variants.map((variant) => <option key={variant.id} value={variant.id}>{variant.name} — ₹{variant.price}</option>)}</select></label>}
          <label><span>Quantity</span><input type="number" min="1" step="1" required value={item.quantity} onChange={(e) => setCreateItem(index, "quantity", e.target.value)} /></label>
          <div className="button-row"><button type="button" onClick={() => setCreateItems((previous) => previous.filter((_, i) => i !== index))} disabled={createBusy || createItems.length === 1}>Remove line</button></div>
        </div>)}
        <div className="button-row"><button type="button" onClick={() => setCreateItems((previous) => [...previous, { product_id: "", variant_id: "", quantity: 1 }])} disabled={createBusy || createItems.length >= 100}>Add product</button><strong>Estimated subtotal: {money(estimatedTotal)}</strong></div>
        <div className="button-row"><button className="sk-btn-primary" type="submit" disabled={createBusy || !products.length}>{createBusy ? "Creating order..." : "Create order"}</button></div>
      </form>}

      <form className="sk-card ord-filters" onSubmit={apply}>
        <label><span><Calendar size={15} /> From</span>
          <input type="date" value={draft.from_date} onChange={(e) => set('from_date', e.target.value)} /></label>
        <label><span>To</span>
          <input type="date" value={draft.to_date} onChange={(e) => set('to_date', e.target.value)} /></label>
        <label><span><Filter size={15} /> Status</span>
          <select value={draft.status} onChange={(e) => set('status', e.target.value)}>
            <option value="all">All Statuses</option>
            {(filters.statuses || []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select></label>
        <label><span><Palette size={15} /> Color Code</span>
          <select value={draft.color_code} onChange={(e) => set('color_code', e.target.value)}>
            <option value="">All Colors</option>
            {(filters.color_codes || []).map((c) => <option key={c} value={c}>{c}</option>)}
          </select></label>
        <label><span><Warehouse size={15} /> Warehouse</span>
          <select value={draft.warehouse_id} onChange={(e) => set('warehouse_id', e.target.value)}>
            <option value="">All Warehouses</option>
            {(filters.warehouses || []).map((w) => <option key={w} value={w}>{w}</option>)}
          </select></label>        <label><span><UserCheck size={15} /> Delivery Boy</span>
          <select value={draft.delivery_boy_id} onChange={(e) => set('delivery_boy_id', e.target.value)}>
            <option value="">All Delivery Boys</option>
            {boys.map((boy) => <option key={boy.id} value={boy.id}>{boy.fullname}</option>)}
          </select></label>
        <div className="button-row">
          <button type="submit" className="sk-btn-primary" disabled={loading}><Search size={16} /> Apply</button>
          <button type="button" onClick={reset} disabled={loading}><X size={16} /> Reset</button>
        </div>
      </form>

      {canAssign && (
        <div className="sk-card ord-assign">
          <label className="ord-check"><input type="checkbox" checked={allSelected} onChange={() => setSelected(allSelected ? [] : orders.map((o) => o.id))} disabled={orders.length === 0} /> Select All</label>
          <strong>Assign Delivery Boy:</strong>
          <select aria-label="Delivery boy" value={boyId} onChange={(e) => setBoyId(e.target.value)}>
            <option value="">-- Select --</option>
            {boys.map((b) => <option key={b.id} value={b.id}>{b.fullname}</option>)}
          </select>
          <button type="button" className="sk-btn-primary" onClick={assign} disabled={assigning || selected.length === 0 || !boyId}><UserCheck size={16} /> {assigning ? 'Assigning...' : 'Assign'}</button>
          {selected.length > 0 && <span className="sk-muted">{selected.length} selected</span>}
        </div>
      )}

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}

      <div className="ord-stats">
        <article className="ord-stat ord-stat-green">
          <div><strong>{stats.total_orders}</strong><span>{labelOrders}</span></div>
          <i><ShoppingCart size={26} /></i>
        </article>
        <article className="ord-stat ord-stat-green">
          <div><strong>{money(stats.revenue)}</strong><span>{labelRevenue}</span><small>Based on the currently applied filters</small></div>
          <i><IndianRupee size={26} /></i>
        </article>
        <article className="ord-stat ord-stat-amber">
          <div><strong>{stats.pending_orders}</strong><span>{labelPending}</span></div>
          <i className="ord-amber"><Clock size={26} /></i>
        </article>
      </div>

      <section className="sk-card sk-flush">
        <div className="ord-list-head">
          <h2><List size={22} /> All Orders</h2>
          <span className="sk-muted">{data?.count ?? 0} orders</span>
        </div>
        {loading && <p className="empty" role="status">Loading orders...</p>}
        {!loading && !error && orders.length === 0 && <p className="empty">No orders match these filters.</p>}
        {orders.length > 0 && (
          <div className="table-wrap">
            <table className="sk-table sk-upper-head">
              <thead>
                <tr>
                  {canAssign && <th><span className="sr-only">Select</span></th>}
                  <th>Order ID</th><th>Date &amp; Time</th><th>Customer</th><th>Items</th><th>Amount Payable</th><th>Method</th><th>Status</th><th>Delivery Boy</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    {canAssign && <td><input type="checkbox" aria-label={'Select order ' + o.id} checked={selected.includes(o.id)} onChange={() => toggle(o.id)} /></td>}
                    <td><strong>#{o.id}</strong></td>
                    <td>{formatDateTime(o.order_date)}</td>
                    <td>{o.customer}</td>
                    <td>{o.items}</td>
                    <td title={o.payable_amount != null ? (o.credit_recorded ? "Final amount payable: subtotal after discount + GST + delivery - VIP - recorded credit" : "Amount payable before monthly credit (no credit deduction recorded)") : "Recorded subtotal after discount; the final payable amount is not available for this order"}>{money(o.payable_amount ?? o.total_amount)}{o.payable_amount == null && <span className="sk-muted"> (subtotal)</span>}</td>
                    <td>{o.payment_method}</td>
                    <td><span className={statusClass(o.status)}>{o.status}</span></td>
                    <td>{o.delivery_boy_name || <span className="sk-muted">Not assigned</span>}</td>
                    <td><div className="ord-row-actions"><button type="button" className="ord-view" onClick={() => navigate('/orders/' + o.id + '?mode=view')}><Eye size={15} /> View</button>{canAssign && <button type="button" className="ord-edit" onClick={() => navigate('/orders/' + o.id + '?mode=edit')}><Pencil size={15} /> Edit</button>}{canAssign && <button type="button" className="ord-delete" onClick={() => deleteOrder(o)} disabled={assigning}><Trash2 size={15} /> Delete</button>}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
