export function validateOrderLines(items, products = []) {
  if (!Array.isArray(items) || items.length === 0) return 'Add at least one order item.';
  const seen = new Set();
  for (const item of items) {
    const productId = String(item?.product_id ?? '').trim();
    const quantity = Number(item?.quantity);
    if (!productId || !Number.isInteger(quantity) || quantity <= 0) {
      return 'Choose a product and enter a positive whole-number quantity for every line.';
    }
    const product = products.find((row) => String(row.id) === productId);
    const variantId = String(item?.variant_id ?? '').trim();
    if (product?.variants?.length && !variantId) return 'Choose a variant for each product that has variants.';
    if (variantId && !product?.variants?.some((variant) => String(variant.id) === variantId)) return 'Choose a valid variant for the selected product.';
    const key = productId + ':' + (variantId || 'base');
    if (seen.has(key)) return 'Each product/variant combination can appear only once. Increase its quantity instead of adding a duplicate line.';
    seen.add(key);
  }
  return '';
}

export function money(value) {
  const n = Number(value);
  const safe = Number.isFinite(n) ? n : 0;
  return '\u20B9' + safe.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatDateTime(value) {
  if (!value) return '\u2014';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const date = d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
  const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  return date + ' ' + time;
}

export function statusClass(status) {
  const s = String(status || '').trim().toLowerCase();
  if (['placed', 'delivered', 'fulfilled'].includes(s)) return 'ord-pill ord-pill-green';
  if (['processing', 'await_pickup', 'picked_up', 'shipped'].includes(s)) return 'ord-pill ord-pill-blue';
  if (['pending'].includes(s)) return 'ord-pill ord-pill-amber';
  if (['cancelled', 'failed'].includes(s)) return 'ord-pill ord-pill-red';
  return 'ord-pill';
}

// Mirrors ROLE_STATUS_LIMITS in django_backend/adminapi/order_pages.py (the backend is the authority).
export const ROLE_STATUS_LIMITS = {
  SALESMAN: ['processing'],
  WAREHOUSE_STAFF: ['processing', 'await_pickup', 'picked_up', 'shipped'],
  DELIVERY_BOY: ['delivered', 'failed'],
};

export function allowedStatusOptions(options, role) {
  const limit = ROLE_STATUS_LIMITS[role];
  if (!limit) return options;
  return options.filter((o) => limit.includes(String(o.value).toLowerCase()));
}
