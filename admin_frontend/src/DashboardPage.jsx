import React from 'react';
import { Package, ShoppingCart, User, IndianRupee, Receipt, TriangleAlert } from 'lucide-react';
import api from './api';

const money = (value) => '₹' + Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function StatCard({ label, value, icon }) {
  return <article className="sk-stat"><div><span>{label}</span><strong>{value}</strong></div><span className="sk-stat-icon" aria-hidden="true">{icon}</span></article>;
}

export default function DashboardPage() {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let active = true;
    api.get('dashboard')
      .then((response) => { if (active) setData(response.data); })
      .catch((err) => { if (active) setError(err.response?.data?.detail || err.response?.data?.message || 'Could not load the dashboard.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  if (loading) return <p className="empty" role="status">Loading dashboard…</p>;
  if (error) return <p className="error" role="alert">{error}</p>;
  const recent = data?.recent_orders || [];
  const lowStock = data?.low_stock || [];
  return <div className="sk-page">
    <div className="sk-stats">
      <StatCard label="Products" value={data.products} icon={<Package size={22} />} />
      <StatCard label="Orders" value={data.orders} icon={<ShoppingCart size={22} />} />
      <StatCard label="Customers" value={data.customers} icon={<User size={22} />} />
      <StatCard label="Revenue" value={money(data.revenue)} icon={<IndianRupee size={22} />} />
    </div>
    <div className="sk-two-col">
      <section className="sk-card">
        <h2><Receipt size={20} /> Recent Orders</h2>
        <div className="table-wrap"><table className="sk-table">
          <thead><tr><th>ID</th><th>Customer</th><th>Status</th><th>Total</th></tr></thead>
          <tbody>
            {recent.map((order) => <tr key={order.order_id}><td>{order.order_id}</td><td>{order.full_name}</td><td><span className="sk-pill">{order.status}</span></td><td>{money(order.total_amount)}</td></tr>)}
            {recent.length === 0 && <tr><td colSpan="4" className="empty">No orders yet.</td></tr>}
          </tbody>
        </table></div>
      </section>
      <section className="sk-card">
        <h2><TriangleAlert size={20} /> Low Stock</h2>
        <div className="table-wrap"><table className="sk-table">
          <thead><tr><th>Product</th><th>Variant</th><th>Stock</th></tr></thead>
          <tbody>
            {lowStock.map((row) => <tr key={row.variant_id}><td>{row.product}</td><td>{row.variant}</td><td>{row.stock}</td></tr>)}
            {lowStock.length === 0 && <tr><td colSpan="3" className="empty">No low-stock variants.</td></tr>}
          </tbody>
        </table></div>
      </section>
    </div>
  </div>;
}
