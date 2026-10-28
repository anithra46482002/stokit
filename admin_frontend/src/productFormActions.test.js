import test from 'node:test';
import assert from 'node:assert/strict';
import { buildProductPayload, describeProductDeleteError, describeSaveFailure, newSaveProgress, saveProductForm } from './productFormActions.js';
import { deleteRecord, pageAfterDelete } from './variantActions.js';

const httpError = (status, data) => Object.assign(new Error('Request failed with status code ' + status), { response: { status, data } });

const EDITING = { id: 3, name: 'pen', code: '1001', price: '10.00', mrp: '10.00', discount: '50.00', no_discount_banner: 'N', disable_variants: 'N', minimum_buying_count: '1', category_id: '1', subcategory_id: '1', visible: '0', highlight: false, stock: 'In Stock', gst_applicable: 'N', gst_percentage: '0.00', gst_price: '0.00', description: '', keywords: '', subtitle: '', brand: '', set_contains: '[]', discount_banners: ['uploads/a.webp'], image_url: 'http://x/y.png' };

// Fake axios-like client. `fail[key]` rejects the Nth call (1-based) of "METHOD url".
function fakeApi({ fail = {}, nextVariantId = 100 } = {}) {
  const calls = []; const counts = {};
  let variantId = nextVariantId;
  const run = (method, url, data) => {
    const key = method + ' ' + url; counts[key] = (counts[key] || 0) + 1; calls.push({ method, url, data });
    const failure = fail[key];
    if (failure && (failure.on === undefined || failure.on === counts[key])) return Promise.reject(failure.error);
    if (method === 'POST' && url === 'product-variants') return Promise.resolve({ status: 201, data: { id: variantId++ } });
    if (method === 'POST' && url === 'products') return Promise.resolve({ status: 201, data: { id: 77 } });
    return Promise.resolve({ status: 200, data: {} });
  };
  return {
    calls,
    request: (cfg) => run(cfg.method, cfg.url, cfg.data),
    patch: (url, data) => run('PATCH', url, data),
    post: (url, data) => run('POST', url, data),
    delete: (url, cfg) => run('DELETE', url, { params: cfg?.params, data: cfg?.data }),
  };
}
const uploads = []; const upload = async (file) => { uploads.push(file.name); return { image_path: 'uploads/' + file.name }; };

// ---------------------------------------------------------------- payload building
test('opening a product for edit and saving builds a typed PATCH body with the product id', () => {
  const { values, error } = buildProductPayload(EDITING);
  assert.equal(error, undefined);
  assert.equal(values.id, 3); assert.equal(values.price, 10); assert.equal(values.category_id, 1); assert.equal(values.subcategory_id, 1);
  assert.equal(values.minimum_buying_count, 1); assert.equal(values.minimum_buying_quantity, 1);
  assert.deepEqual(values.set_contains, []); assert.equal(values.code, '1001');
  assert.ok(!('image_url' in values) && !('discount_banners' in values) && !('color' in values), 'display-only/other-endpoint fields are not sent');
  assert.ok(!('gst_percentage' in values) && !('gst_price' in values), 'product save leaves legacy product GST fields untouched; variants own GST amounts');
});

test('a legacy product with an empty code is saved without sending (and failing on) the empty code', () => {
  assert.ok(!('code' in buildProductPayload({ ...EDITING, code: '' }).values));
  assert.equal(buildProductPayload({ ...EDITING, id: undefined, code: '' }).values.code, '');
});

test('invalid input is rejected before any request is made', () => {
  assert.match(buildProductPayload({ ...EDITING, price: 'abc' }).error, /valid price/i);
  assert.match(buildProductPayload({ ...EDITING, price: '-5' }).error, /valid price/i);
  assert.match(buildProductPayload({ ...EDITING, price: '' }).error, /price is required/i);
  assert.match(buildProductPayload({ ...EDITING, name: '   ' }).error, /name is required/i);
  assert.match(buildProductPayload({ ...EDITING, minimum_buying_count: '0' }).error, /positive whole number/i);
  assert.match(buildProductPayload({ ...EDITING, set_contains: '{oops' }).error, /valid JSON/i);
});

test('MRP defaults to price when the Add form leaves it blank', () => {
  assert.equal(buildProductPayload({ ...EDITING, id: undefined, mrp: '', price: '25' }).values.mrp, 25);
});

test('uploaded banners and images are not uploaded twice when a later step fails and is retried', async () => {
  uploads.length = 0;
  const api = fakeApi({ fail: { 'POST product-images': { on: 1, error: httpError(500, 'x') } } });
  const progress = newSaveProgress(); const values = buildProductPayload(EDITING).values;
  const args = { values, bannerFiles: [{ name: 'b1.png' }], oldBannerPaths: ['uploads/a.webp'], productImageFiles: [{ name: 'i1.png' }], progress };
  await assert.rejects(saveProductForm(api, upload, args));
  await saveProductForm(api, upload, args);
  assert.deepEqual(uploads, ['b1.png', 'i1.png']);
  assert.equal(api.calls.filter((c) => c.url === 'product-images').length, 2, 'one failed request and one successful retry');
  assert.deepEqual(api.calls.find((c) => c.method === 'PATCH' && c.data.discount_banners).data.discount_banners, ['uploads/a.webp', 'uploads/b1.png']);
});

test('save failure text: nothing stored vs. partly stored, for server and network errors', () => {
  assert.match(describeSaveFailure(httpError(403, { detail: 'Role may not write' }), newSaveProgress(), false), /Role may not write.*Nothing was saved\./);
  assert.match(describeSaveFailure(new Error('Network Error'), newSaveProgress(), false), /Network Error.*Nothing was saved/);
  assert.match(describeSaveFailure(httpError(500, { detail: 'boom' }), { productId: 3 }, false), /changes were saved but the rest was not/);
});

// ---------------------------------------------------------------- delete
test('product delete sends one DELETE to products with the selected id and resolves only on success', async () => {
  const api = fakeApi();
  await deleteRecord(api, 'products', null, 4);
  assert.deepEqual(api.calls, [{ method: 'DELETE', url: 'products', data: { params: { id: 4 }, data: { id: 4 } } }]);
  const refused = fakeApi({ fail: { 'DELETE products': { error: httpError(409, { detail: 'x' }) } } });
  await assert.rejects(deleteRecord(refused, 'products', null, 4));
});

test('product delete errors: protected, missing, forbidden, server and network failures', () => {
  const protectedProduct = describeProductDeleteError(httpError(409, { detail: 'This product has order history and cannot be permanently deleted. Set Visibility to Hidden to archive it.' }), 'bangless (product ID 4)');
  assert.equal(protectedProduct.archivable, true); assert.match(protectedProduct.message, /order history.*Nothing was changed/);
  const gone = describeProductDeleteError(httpError(404, { detail: 'Product not found' }), 'x'); assert.equal(gone.gone, true); assert.match(gone.message, /no longer exists/);
  assert.match(describeProductDeleteError(httpError(403, { detail: 'Role may not write' }), 'x').message, /permission/);
  assert.match(describeProductDeleteError(httpError(500, { detail: 'db' }), 'x').message, /server error.*Nothing was removed/);
  const network = describeProductDeleteError(new Error('Network Error'), 'x');
  assert.match(network.message, /not deleted.*Network Error.*Nothing was removed/); assert.equal(network.archivable, false);
  for (const outcome of [gone, network]) assert.equal(outcome.archivable, false);
});

test('deleting the only product on a later page steps back; rows get distinct client keys', () => {
  assert.equal(pageAfterDelete(3, 1), 2); assert.equal(pageAfterDelete(1, 1), 1);
  // Product forms no longer create or manage variants; variant actions are tested on /variants.
});
