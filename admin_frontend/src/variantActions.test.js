import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { apiErrorText, deleteConfirmMessage, deleteRecord, describeDeleteError, describeLoadError, describeVariant, fetchVariant, pageAfterDelete, variantViewRows, withoutReadOnlyVariantKeys } from './variantActions.js';
import { saveVariantAndParent } from './productSettings.js';

const httpError = (status, data) => Object.assign(new Error('Request failed with status code ' + status), { response: { status, data } });
const LABEL = 'Red pen (variant ID 8, product ID 3)';

// ---- fake axios-like client that records every request
function fakeApi({ failOn = {} } = {}) {
  const calls = [];
  const respond = (key, payload) => { calls.push(payload); if (failOn[key]) return Promise.reject(failOn[key]); return Promise.resolve({ status: 200, data: {} }); };
  return {
    calls,
    request: (cfg) => respond('request', { method: cfg.method, url: cfg.url, data: cfg.data }),
    delete: (url, cfg) => respond('delete', { method: 'DELETE', url, params: cfg?.params, data: cfg?.data }),
    patch: (url, data) => respond('patch', { method: 'PATCH', url, data }),
    get: (url, cfg) => { calls.push({ method: 'GET', url, params: cfg?.params }); return Promise.resolve({ data: { results: [{ id: Number(cfg.params.id), no_discount_banner: 'N', disable_variants: 'N' }] } }); },
  };
}

// ---------------------------------------------------------------- helpers
test('error text prefers the server detail and is never a raw JSON blob', () => {
  assert.equal(apiErrorText(httpError(409, { detail: 'Some conflict' })), 'Some conflict');
  assert.equal(apiErrorText(httpError(400, { name: 'Name cannot be empty' })), 'name: Name cannot be empty');
  assert.ok(!apiErrorText(httpError(409, { detail: 'x' })).includes('{'));
});

test('delete errors: referenced, missing, forbidden, server and network failures are all explained honestly', () => {
  assert.match(describeDeleteError(httpError(409, { detail: 'Some other conflict' }), LABEL), /was not deleted: Some other conflict/);
  assert.match(describeDeleteError(httpError(404, { detail: 'Variant not found' }), LABEL), /no longer exists.*refreshed/);
  assert.match(describeDeleteError(httpError(403, { detail: 'An active administrator role assignment is required for this operation.' }), LABEL), /permission/);
  assert.match(describeDeleteError(httpError(500, { detail: 'Variant could not be deleted. Nothing was removed.' }), LABEL), /server error. Nothing was removed/);
  assert.match(describeDeleteError(new Error('Network Error'), LABEL), /Network Error.*Nothing was removed/);
  for (const e of [httpError(409, { detail: 'x' }), httpError(404, {}), new Error('Network Error')]) assert.ok(!/successfully|deleted successfully/i.test(describeDeleteError(e, LABEL)));
});

test('the confirmation label identifies the variant and its product', () => {
  assert.equal(describeVariant({ id: 8, name: 'Red pen', product_id: 3 }), LABEL);
});

test('deleting the last row of a later page steps back one page', () => {
  assert.equal(pageAfterDelete(3, 1), 2);
  assert.equal(pageAfterDelete(3, 20), 3);
  assert.equal(pageAfterDelete(1, 1), 1);
  assert.equal(pageAfterDelete(2, 0), 1);
});

// ---------------------------------------------------------------- delete flow (integration with the request layer)
test('delete sends one authenticated-client DELETE to product-variants with the selected variant id only', async () => {
  const api = fakeApi();
  await deleteRecord(api, 'product-variants', undefined, 8);
  assert.deepEqual(api.calls, [{ method: 'DELETE', url: 'product-variants', params: { id: 8 }, data: { id: 8 } }]);
});

test('a refused delete rejects, so the caller can keep the row and show the error', async () => {
  const api = fakeApi({ failOn: { delete: httpError(500, { detail: 'Variant could not be deleted. Nothing was removed.' }) } });
  await assert.rejects(deleteRecord(api, 'product-variants', undefined, 3), (err) => err.response.status === 500);
  assert.equal(api.calls.length, 1); // no retry, no second request
});

// ---------------------------------------------------------------- edit flow
const editValues = { id: 8, product_id: 3, name: 'Red pen', variant_price: 100, mrp: 110, quantity: 99, discount: '15', gst: 'N', gst_price: 0, minimum_buying_count: 1 };
const sameParent = { no_discount_banner: 'N', disable_variants: 'N' };

test('edit sends PATCH product-variants with the variant id and no parent-product fields', async () => {
  const api = fakeApi();
  await saveVariantAndParent({ api, values: { ...editValues, ...sameParent }, parentSettings: sameParent, original: sameParent });
  const patch = api.calls.find((c) => c.method === 'PATCH' && c.url === 'product-variants');
  assert.ok(patch, 'PATCH product-variants was sent');
  assert.equal(patch.data.id, 8);
  assert.equal(patch.data.product_id, 3);
  assert.ok(!('disable_variants' in patch.data) && !('no_discount_banner' in patch.data));
  assert.ok(!api.calls.some((c) => c.url === 'products' && c.method === 'PATCH'), 'unchanged parent settings are not re-saved');
});

test('a rejected edit does not report success and does not touch the parent product', async () => {
  const api = fakeApi({ failOn: { request: httpError(400, { quantity: 'Must be non-negative' }) } });
  await assert.rejects(saveVariantAndParent({ api, values: { ...editValues, quantity: -1, ...sameParent }, parentSettings: sameParent, original: sameParent }), (err) => err.response.status === 400 && !err.partial);
  assert.equal(api.calls.length, 1);
});

test('a parent-settings failure after a stored variant is flagged partial so the UI refreshes the table', async () => {
  const api = fakeApi({ failOn: { patch: httpError(500, { detail: 'boom' }) } });
  const changed = { no_discount_banner: 'Y', disable_variants: 'N' };
  await assert.rejects(saveVariantAndParent({ api, values: { ...editValues, ...changed }, parentSettings: changed, original: sameParent }), (err) => err.partial === true && /variant was saved/.test(err.message));
  assert.ok(api.calls.some((c) => c.url === 'product-variants' && c.method === 'PATCH'));
});

// ---------------------------------------------------------------- no in-use pre-block (referenced variants can be deleted)
test('the in-use pre-block helpers no longer exist and App.jsx no longer uses them', async () => {
  const actions = await import('./variantActions.js');
  assert.equal(actions.blockedDeleteMessage, undefined);
  assert.equal(actions.deleteBlockedReason, undefined);
  const app = readFileSync(new URL('./App.jsx', import.meta.url), 'utf8');
  assert.ok(!/blockedDeleteMessage|deleteBlockedReason/.test(app));
  assert.ok(!/cannot be permanently deleted because it is still used/.test(readFileSync(new URL('./variantActions.js', import.meta.url), 'utf8')));
});

test('the remove() flow in App.jsx confirms first and then always sends the DELETE (no early return for in-use rows)', () => {
  const app = readFileSync(new URL('./App.jsx', import.meta.url), 'utf8');
  const body = app.slice(app.indexOf('async function remove(row)'), app.indexOf('async function showOrder'));
  assert.match(body, /window\.confirm\(/);
  assert.match(body, /await deleteRecord\(/);
  assert.ok(!/in_use/.test(body), 'delete execution path must not look at in_use');
  assert.ok(body.indexOf('window.confirm(') < body.indexOf('await deleteRecord('));
  assert.match(body, /deletingRef\.current/); // duplicate-request guard stays
  assert.ok(body.indexOf('await deleteRecord(') < body.indexOf('await load()'), 'list refreshes only after the confirmed delete');
});

test('delete confirmation does not include reference-based conditions', () => {
  const msg = deleteConfirmMessage({ id: 2, name: 'Box', product_id: 3, in_use: 'order history, customer carts, inventory history' });
  assert.match(msg, /Permanently delete variant/);
  assert.match(msg, /cannot be undone/);
  assert.ok(!/referenced by|order history|customer carts|inventory history|cannot be deleted|cannot be permanently deleted/.test(msg));
});

test('unreferenced and referenced variants receive the same simple confirmation', () => {
  const plain = deleteConfirmMessage({ id: 9, name: 'Free', product_id: 3, in_use: '' });
  const referenced = deleteConfirmMessage({ id: 9, name: 'Free', product_id: 3, in_use: 'customer carts' });
  assert.equal(plain, referenced);
});

// ---------------------------------------------------------------- view / edit load the saved record
test('fetchVariant GETs the saved record by id and returns it', async () => {
  const calls = [];
  const api = { get: async (url, cfg) => { calls.push([url, cfg.params]); return { data: { id: 8, name: 'Red pen', product_id: 3 } }; } };
  const record = await fetchVariant(api, 'product-variants', 8);
  assert.deepEqual(calls, [['product-variants', { id: 8 }]]);
  assert.equal(record.name, 'Red pen');
});

test('fetchVariant rejects when the server answers for another variant or with nothing', async () => {
  await assert.rejects(fetchVariant({ get: async () => ({ data: { id: 9 } }) }, 'product-variants', 8), /did not return variant ID 8/);
  await assert.rejects(fetchVariant({ get: async () => ({ data: { results: [] } }) }, 'product-variants', 8), /did not return variant ID 8/);
  await assert.rejects(fetchVariant({ get: async () => { throw httpError(404, { detail: 'Variant not found' }); } }, 'product-variants', 8), (e) => e.response.status === 404);
});

test('load errors: a missing record refreshes the list; other failures are explained', () => {
  const missing = describeLoadError(httpError(404, { detail: 'Variant not found' }), 8);
  assert.equal(missing.refresh, true);
  assert.match(missing.message, /Variant ID 8 no longer exists/);
  assert.equal(describeLoadError(httpError(500, { detail: 'boom' }), 8).refresh, false);
  assert.match(describeLoadError(httpError(403, { detail: 'nope' }), 8).message, /permission/);
  assert.match(describeLoadError(new Error('Network Error'), 8).message, /Network Error/);
});

test('the View rows show id, parent product, name, price, MRP, quantity, GST and minimum quantity from the saved record', () => {
  const rows = Object.fromEntries(variantViewRows({ id: 8, product_id: 3, product_name: 'Pens', name: 'Red pen', price: '100.00', mrp: '110.00', quantity: 99, discount: '15', gst: 'Y', gst_price: '5.00', minimum_buying_count: 2, in_use: 'order history' }));
  assert.equal(rows['Variant ID'], '8');
  assert.equal(rows['Parent product'], 'Pens (product ID 3)');
  assert.equal(rows['Variant name'], 'Red pen');
  assert.equal(rows['Price'], '100.00');
  assert.equal(rows['MRP'], '110.00');
  assert.equal(rows['Quantity'], '99');
  assert.equal(rows['GST applicable'], 'Yes');
  assert.equal(rows['GST amount'], '5.00');
  assert.equal(rows['Minimum purchase quantity'], '2');
  assert.equal(rows['Referenced by'], 'order history');
  assert.equal(Object.fromEntries(variantViewRows({ id: 1, product_id: 4, gst: 'N' }))['Parent product'], 'Product ID 4');
});

test('read-only list fields are removed before a save so nothing unsupported is sent', () => {
  const out = withoutReadOnlyVariantKeys({ id: 8, name: 'x', in_use: 'order history', product_name: 'Pens', minimum_buying_count: 3 });
  assert.deepEqual(out, { id: 8, name: 'x', minimum_buying_count: 3 });
});
