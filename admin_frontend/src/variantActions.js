// Pure helpers for the product-variant View/Edit/Delete UI (kept free of React so they are unit-testable).
import { describeApiError } from './productSettings.js';

// The server's `detail` string when there is one, otherwise the field errors flattened to text.
// Never a raw JSON blob.
export function apiErrorText(err) {
  const body = err?.response?.data;
  if (body && typeof body === 'object' && typeof body.detail === 'string') return body.detail;
  return describeApiError(err);
}

// Honest, actionable message for a failed delete. `label` identifies the record (name + id).
// A delete is only ever refused for a real reason reported by the server (permission, missing record,
// database failure); being referenced by orders, carts or stock history is NOT one of them.
export function describeDeleteError(err, label) {
  const status = err?.response?.status;
  if (!err?.response) {
    return `"${label}" was not deleted: ${err?.message || 'the server could not be reached'}. Nothing was removed; check the connection and try again.`;
  }
  const detail = apiErrorText(err);
  if (status === 404) return `"${label}" no longer exists (it may already have been deleted). The list has been refreshed.`;
  if (status === 401 || status === 403) return `"${label}" was not deleted: you do not have permission for this action (${detail}).`;
  if (status >= 500) return `"${label}" was not deleted because of a server error. Nothing was removed. ${detail}`;
  return `"${label}" was not deleted: ${detail}`;
}

// After removing a row: step back one page when the deleted row was the only one on a later page,
// so the admin is not left looking at an empty page.
export function pageAfterDelete(page, rowCountOnPage) {
  return page > 1 && rowCountOnPage <= 1 ? page - 1 : page;
}

export function describeVariant(row) {
  return `${row?.name ?? 'Variant'} (variant ID ${row?.id}, product ID ${row?.product_id})`;
}

// The exact DELETE request the admin list sends: id both as a query parameter and in the JSON body,
// authenticated by the shared client's interceptor. Resolves only when the server confirmed (2xx).
export async function deleteRecord(api, endpoint, moduleParams, id) {
  return api.delete(endpoint, { params: { ...(moduleParams || {}), id }, data: { ...(moduleParams || {}), id } });
}

// Text of the confirmation dialog shown BEFORE the DELETE request. It informs; it never prevents the request.
// `in_use` (from the list API, e.g. "order history, customer carts") only changes what the admin is told.
export function deleteConfirmMessage(row) {
  const label = describeVariant(row);
  return 'Permanently delete variant ' + label + '? This action cannot be undone.';
}

// Fields the list API adds for display only. They are never part of a save (the API rejects unknown fields).
export const VARIANT_READ_ONLY_KEYS = ['in_use', 'product_name'];

export function withoutReadOnlyVariantKeys(values) {
  const out = { ...(values || {}) };
  VARIANT_READ_ONLY_KEYS.forEach((key) => { delete out[key]; });
  return out;
}

// Loads the saved record from the API (GET product-variants?id=) instead of trusting the row the list holds.
// Rejects, with the server's error attached, when the record is missing or the answer is for another variant.
export async function fetchVariant(api, endpoint, id) {
  const response = await api.get(endpoint, { params: { id } });
  const payload = response?.data;
  // Support both detail-shaped responses and paginated-list responses from deployments
  // where the backend route has not yet picked up the detail-query implementation.
  const candidates = Array.isArray(payload?.results) ? payload.results : [payload];
  const record = candidates.find((item) => item && typeof item === 'object' && String(item.id ?? item.variant_id) === String(id));
  if (!record) {
    throw new Error(`The server did not return variant ID ${id}.`);
  }
  return { ...record, id: record.id ?? record.variant_id };
}

// Message for a failed View/Edit load. A 404 also tells the caller to refresh the list (`refresh: true`).
export function describeLoadError(err, id) {
  const status = err?.response?.status;
  if (!err?.response) {
    return { refresh: false, message: `Variant ID ${id} could not be loaded: ${err?.message || 'the server could not be reached'}. Check the connection and try again.` };
  }
  if (status === 404) return { refresh: true, message: `Variant ID ${id} no longer exists (it may have been deleted). The list has been refreshed.` };
  if (status === 401 || status === 403) return { refresh: false, message: `Variant ID ${id} could not be loaded: you do not have permission for this action (${apiErrorText(err)}).` };
  return { refresh: false, message: `Variant ID ${id} could not be loaded: ${apiErrorText(err)}` };
}

// Label/value pairs for the read-only View dialog, straight from the saved record.
export function variantViewRows(record) {
  const yesNo = (value) => (String(value ?? '').toUpperCase() === 'Y' ? 'Yes' : String(value ?? '').toUpperCase() === 'N' ? 'No' : '—');
  const text = (value) => (value === null || value === undefined || value === '' ? '—' : String(value));
  return [
    ['Variant ID', text(record?.id)],
    ['Parent product', record?.product_name ? `${record.product_name} (product ID ${record.product_id})` : `Product ID ${text(record?.product_id)}`],
    ['Variant name', text(record?.name)],
    ['Price', text(record?.price)],
    ['MRP', text(record?.mrp)],
    ['Quantity', text(record?.quantity)],
    ['Discount (%)', text(record?.discount)],
    ['GST applicable', yesNo(record?.gst)],
    ['GST amount', text(record?.gst_price)],
    ['Minimum purchase quantity', text(record?.minimum_buying_count)],
    ['Referenced by', record?.in_use ? String(record.in_use) : 'nothing'],
  ];
}
