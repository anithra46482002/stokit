import test from 'node:test';
import assert from 'node:assert/strict';
import {
  IDLE_PARENT_STATE, PARENT_FIELDS, PARENT_NOT_LOADED_MESSAGE, PRODUCT_SETTING_FIELDS, YN_OPTIONS,
  createParentSettingsLoader, fetchParentSettings, parentSaveBlocker, saveVariantAndParent, stripParentFields,
  MINIMUM_BUYING_QUANTITY_DEFAULT, MINIMUM_BUYING_QUANTITY_FIELD, MINIMUM_BUYING_QUANTITY_MESSAGE,
  validateMinimumBuyingQuantity, minimumBuyingQuantityFormValue, withMinimumBuyingQuantity, describeApiError,
} from './productSettings.js';

// Fake API client over an in-memory synthetic product table (no real data, no network).
function fakeApi(products, { failProductPatch = false, ignoreProductPatch = false, failVariant = false } = {}) {
  const calls = [];
  return {
    calls,
    products,
    async get(url, config) {
      calls.push({ method: 'GET', url, params: config?.params });
      const rows = Object.values(products).filter((p) => String(p.id) === String(config.params.id));
      return { data: { count: rows.length, results: rows.map((p) => ({ ...p })) } };
    },
    async patch(url, data) {
      calls.push({ method: 'PATCH', url, data });
      if (failProductPatch) { const err = new Error('Request failed'); err.response = { data: { disable_variants: 'disable_variants must be Y or N' } }; throw err; }
      if (!ignoreProductPatch) Object.assign(products[data.id], data);
      return { data: products[data.id] };
    },
    async request(config) {
      calls.push({ method: config.method, url: config.url, data: config.data });
      if (failVariant) { const err = new Error('Request failed'); err.response = { data: { name: 'Variant name is required' } }; throw err; }
      return { data: { id: 1 } };
    },
  };
}

const product = (id, discount, disable) => ({ id, name: 'Synthetic ' + id, no_discount_banner: discount, disable_variants: disable });

test('both settings are defined as Y/N dropdowns with exact string values', () => {
  assert.deepEqual(PARENT_FIELDS, ['no_discount_banner', 'disable_variants']);
  assert.deepEqual(YN_OPTIONS, [['N', 'No'], ['Y', 'Yes']]);
  assert.deepEqual(PRODUCT_SETTING_FIELDS.map((f) => [f.key, f.label]), [['no_discount_banner', 'Discount Y/N'], ['disable_variants', 'Disable Variants Y/N']]);
  PRODUCT_SETTING_FIELDS.forEach((f) => assert.deepEqual(f.options, [['N', 'No'], ['Y', 'Yes']]));
});

test('stripParentFields removes both product-level settings and keeps variant fields', () => {
  const rest = stripParentFields({ product_id: 5, name: 'Small', price: 10, no_discount_banner: 'Y', disable_variants: 'N' });
  assert.deepEqual(rest, { product_id: 5, name: 'Small', price: 10 });
});

test('fetchParentSettings loads the actual saved strings of the selected product', async () => {
  const api = fakeApi({ 1: product(1, 'N', 'N'), 2: product(2, 'Y', 'N'), 3: product(3, 'N', 'Y'), 4: product(4, 'Y', 'Y') });
  assert.deepEqual(await fetchParentSettings(api, 1), { no_discount_banner: 'N', disable_variants: 'N' });
  assert.deepEqual(await fetchParentSettings(api, '2'), { no_discount_banner: 'Y', disable_variants: 'N' });
  assert.deepEqual(await fetchParentSettings(api, 3), { no_discount_banner: 'N', disable_variants: 'Y' });
  assert.deepEqual(await fetchParentSettings(api, 4), { no_discount_banner: 'Y', disable_variants: 'Y' });
  assert.deepEqual(api.calls[0].params, { id: 1, page: 1, page_size: 1 });
});

test('fetchParentSettings rejects a missing product or an unexpected value', async () => {
  await assert.rejects(fetchParentSettings(fakeApi({}), 9), /not found/);
  await assert.rejects(fetchParentSettings(fakeApi({ 1: product(1, 'maybe', 'N') }), 1), /unexpected value/);
});

for (const discount of ['N', 'Y']) {
  for (const disable of ['N', 'Y']) {
    test('saving Discount ' + discount + ' and Disable Variants ' + disable + ' persists exact strings on the parent product only', async () => {
      const startDiscount = discount === 'Y' ? 'N' : 'Y';
      const startDisable = disable === 'Y' ? 'N' : 'Y';
      const api = fakeApi({ 7: product(7, startDiscount, startDisable) });
      const values = { product_id: 7, name: 'Small', price: 10, mrp: 10, quantity: 3, no_discount_banner: discount, disable_variants: disable };
      const saved = await saveVariantAndParent({ api, values, parentSettings: { no_discount_banner: discount, disable_variants: disable }, original: { no_discount_banner: startDiscount, disable_variants: startDisable } });
      assert.deepEqual(saved, { no_discount_banner: discount, disable_variants: disable });
      assert.equal(api.products[7].no_discount_banner, discount);
      assert.equal(api.products[7].disable_variants, disable);
      const variantCall = api.calls.find((c) => c.url === 'product-variants');
      assert.equal(variantCall.method, 'POST');
      assert.ok(!('no_discount_banner' in variantCall.data) && !('disable_variants' in variantCall.data), 'variant payload must exclude product-level fields');
      const productCall = api.calls.find((c) => c.method === 'PATCH' && c.url === 'products');
      assert.equal(productCall.data.id, 7);
      // The variant is written first, the product second, then the product is re-read.
      assert.deepEqual(api.calls.map((c) => c.url), ['product-variants', 'products', 'products']);
    });
  }
}

test('an edit uses PATCH for the variant and skips the product update when settings are unchanged', async () => {
  const api = fakeApi({ 7: product(7, 'Y', 'Y') });
  await saveVariantAndParent({ api, values: { id: 12, product_id: 7, name: 'Small', no_discount_banner: 'Y', disable_variants: 'Y' }, parentSettings: { no_discount_banner: 'Y', disable_variants: 'Y' }, original: { no_discount_banner: 'Y', disable_variants: 'Y' } });
  assert.equal(api.calls[0].method, 'PATCH');
  assert.ok(!api.calls.some((c) => c.method === 'PATCH' && c.url === 'products'), 'no product update when nothing changed');
  assert.equal(api.products[7].no_discount_banner, 'Y');
});

test('only the changed setting is sent so the other setting is never overwritten', async () => {
  const api = fakeApi({ 7: product(7, 'Y', 'N') });
  await saveVariantAndParent({ api, values: { product_id: 7, name: 'Small' }, parentSettings: { no_discount_banner: 'Y', disable_variants: 'Y' }, original: { no_discount_banner: 'Y', disable_variants: 'N' } });
  const productCall = api.calls.find((c) => c.method === 'PATCH' && c.url === 'products');
  assert.deepEqual(productCall.data, { id: 7, disable_variants: 'Y' });
});

test('a failed variant save stops before touching the product', async () => {
  const api = fakeApi({ 7: product(7, 'N', 'N') }, { failVariant: true });
  await assert.rejects(saveVariantAndParent({ api, values: { product_id: 7, name: '' }, parentSettings: { no_discount_banner: 'Y', disable_variants: 'Y' }, original: { no_discount_banner: 'N', disable_variants: 'N' } }), (err) => !err.partial);
  assert.deepEqual(api.calls.map((c) => c.url), ['product-variants']);
  assert.equal(api.products[7].no_discount_banner, 'N');
});

test('a failed product update is reported as a visible partial failure and never as success', async () => {
  const api = fakeApi({ 7: product(7, 'N', 'N') }, { failProductPatch: true });
  const outcome = saveVariantAndParent({ api, values: { product_id: 7, name: 'Small' }, parentSettings: { no_discount_banner: 'N', disable_variants: 'Y' }, original: { no_discount_banner: 'N', disable_variants: 'N' } });
  await assert.rejects(outcome, (err) => err.partial === true && /variant was saved/.test(err.message) && /disable_variants must be Y or N/.test(err.message) && /press Save again/.test(err.message));
  assert.equal(api.products[7].disable_variants, 'N');
});

test('retry after a partial failure only retries the product settings (no duplicate variant)', async () => {
  const api = fakeApi({ 7: product(7, 'N', 'N') });
  await saveVariantAndParent({ api, values: { product_id: 7, name: 'Small' }, parentSettings: { no_discount_banner: 'N', disable_variants: 'Y' }, original: { no_discount_banner: 'N', disable_variants: 'N' }, alreadySaved: true });
  assert.ok(!api.calls.some((c) => c.url === 'product-variants'));
  assert.equal(api.products[7].disable_variants, 'Y');
});

test('verification fails loudly when the server did not store the requested values', async () => {
  const api = fakeApi({ 7: product(7, 'N', 'N') }, { ignoreProductPatch: true });
  await assert.rejects(saveVariantAndParent({ api, values: { product_id: 7, name: 'Small' }, parentSettings: { no_discount_banner: 'Y', disable_variants: 'N' }, original: { no_discount_banner: 'N', disable_variants: 'N' } }), (err) => err.partial === true && /different values for no_discount_banner/.test(err.message));
});

// ---- Settings-loading lifecycle (regression for "settings have not finished loading") ----

const deferredApi = () => {
  const pending = [];
  return {
    pending,
    get(url, config) {
      return new Promise((resolve, reject) => pending.push({ id: config.params.id, resolve, reject }));
    },
  };
};
const reply = (id, discount, disable) => ({ data: { count: 1, results: [{ id, no_discount_banner: discount, disable_variants: disable }] } });
const collect = () => { const states = []; return { states, onState: (s) => states.push(s) }; };

test('regression: calling fetchParentSettings without the API client fails with a clear message', async () => {
  // App.jsx used to call fetchParentSettings(productId), which made every load throw.
  await assert.rejects(fetchParentSettings('5'), /needs the API client/);
  await assert.rejects(fetchParentSettings(undefined, 5), /needs the API client/);
});

test('fetchParentSettings rejects missing or invalid product ids before any request', async () => {
  const api = fakeApi({ 1: product(1, 'N', 'N') });
  for (const bad of ['', undefined, null, 'abc', '0', -3, '1.5']) await assert.rejects(fetchParentSettings(api, bad), /valid product/);
  assert.equal(api.calls.length, 0);
});

test('fetchParentSettings normalises Y/N case and padding but still rejects other values', async () => {
  const api = fakeApi({ 1: product(1, ' y ', 'n') });
  assert.deepEqual(await fetchParentSettings(api, 1), { no_discount_banner: 'Y', disable_variants: 'N' });
  await assert.rejects(fetchParentSettings(fakeApi({ 2: product(2, 'Y', '') }), 2), /unexpected value/);
  await assert.rejects(fetchParentSettings(fakeApi({ 3: product(3, undefined, 'N') }), 3), /unexpected value/);
});

test('fetchParentSettings handles numeric or string ids and unexpected response shapes', async () => {
  const numeric = { async get() { return reply(7, 'Y', 'N'); } };
  const stringId = { async get() { return reply('7', 'Y', 'N'); } };
  assert.deepEqual(await fetchParentSettings(numeric, '7'), { no_discount_banner: 'Y', disable_variants: 'N' });
  assert.deepEqual(await fetchParentSettings(stringId, 7), { no_discount_banner: 'Y', disable_variants: 'N' });
  for (const data of [undefined, {}, { results: [] }, { results: null }]) {
    await assert.rejects(fetchParentSettings({ async get() { return { data }; } }, 7), /not found/);
  }
  // A different product coming back (wrong id) is never accepted as this product's settings.
  await assert.rejects(fetchParentSettings({ async get() { return reply(8, 'Y', 'Y'); } }, 7), /not found/);
});

test('loader: loading then ready for the selected product, with ids as strings', async () => {
  const { states, onState } = collect();
  const loader = createParentSettingsLoader({ api: fakeApi({ 4: product(4, 'Y', 'N') }), onState });
  await loader.load(4);
  assert.deepEqual(states, [
    { status: 'loading', productId: '4', original: null, error: '' },
    { status: 'ready', productId: '4', original: { no_discount_banner: 'Y', disable_variants: 'N' }, error: '' },
  ]);
});

test('loader: a failed request ends in error (never ready) and a retry can then succeed', async () => {
  let fail = true;
  const products = { 4: product(4, 'N', 'Y') };
  const api = { async get(url, config) { if (fail) { const e = new Error('Network Error'); throw e; } return fakeApi(products).get(url, config); } };
  const { states, onState } = collect();
  const loader = createParentSettingsLoader({ api, onState });
  await loader.load(4);
  assert.equal(states.at(-1).status, 'error');
  assert.match(states.at(-1).error, /Network Error/);
  assert.equal(states.at(-1).original, null);
  assert.ok(!states.some((s) => s.status === 'ready'));
  fail = false;
  await loader.load(4); // Retry
  assert.deepEqual(states.at(-1), { status: 'ready', productId: '4', original: { no_discount_banner: 'N', disable_variants: 'Y' }, error: '' });
});

test('loader: a loader built without an API client reports an error instead of hanging in loading', async () => {
  const { states, onState } = collect();
  await createParentSettingsLoader({ api: undefined, onState }).load(4);
  assert.equal(states.at(-1).status, 'error');
  assert.match(states.at(-1).error, /needs the API client/);
});

test('loader: switching products quickly never lets the older response overwrite the newer one', async () => {
  const api = deferredApi();
  const { states, onState } = collect();
  const loader = createParentSettingsLoader({ api, onState });
  const first = loader.load(1);
  const second = loader.load(2);
  assert.deepEqual(api.pending.map((p) => p.id), [1, 2]);
  api.pending[1].resolve(reply(2, 'N', 'Y'));
  await second;
  api.pending[0].resolve(reply(1, 'Y', 'N')); // late response for the previously selected product
  await first;
  const last = states.at(-1);
  assert.deepEqual(last, { status: 'ready', productId: '2', original: { no_discount_banner: 'N', disable_variants: 'Y' }, error: '' });
  assert.ok(!states.some((s) => s.status === 'ready' && s.productId === '1'));
});

test('loader: a late failure of an older product cannot replace the current ready state', async () => {
  const api = deferredApi();
  const { states, onState } = collect();
  const loader = createParentSettingsLoader({ api, onState });
  const first = loader.load(1);
  const second = loader.load(2);
  api.pending[1].resolve(reply(2, 'Y', 'Y'));
  await second;
  api.pending[0].reject(new Error('timeout'));
  await first;
  assert.equal(states.at(-1).status, 'ready');
  assert.equal(states.at(-1).productId, '2');
});

test('loader: cancel and reset discard in-flight responses', async () => {
  const api = deferredApi();
  const { states, onState } = collect();
  const loader = createParentSettingsLoader({ api, onState });
  const pending = loader.load(1);
  loader.cancel();
  api.pending[0].resolve(reply(1, 'Y', 'Y'));
  await pending;
  assert.deepEqual(states.map((s) => s.status), ['loading']);
  const again = loader.load(1);
  loader.reset();
  api.pending[1].resolve(reply(1, 'Y', 'Y'));
  await again;
  assert.deepEqual(states.at(-1), { status: 'idle', productId: '', original: null, error: '' });
});

test('save guard: allowed only when the matching product finished loading with valid Y/N values', () => {
  const ready = { status: 'ready', productId: '9', original: { no_discount_banner: 'N', disable_variants: 'N' }, error: '' };
  const good = { no_discount_banner: 'Y', disable_variants: 'N' };
  assert.equal(parentSaveBlocker(ready, 9, good), '');
  assert.equal(parentSaveBlocker(ready, '9', good), '');
  // still loading, idle, or loaded for another product: blocked with the original message
  assert.equal(parentSaveBlocker({ ...ready, status: 'loading', original: null }, '9', good), PARENT_NOT_LOADED_MESSAGE);
  assert.equal(parentSaveBlocker(IDLE_PARENT_STATE, '9', good), PARENT_NOT_LOADED_MESSAGE);
  assert.equal(parentSaveBlocker(ready, '10', good), PARENT_NOT_LOADED_MESSAGE);
  // invalid or empty Yes/No selections are blocked
  for (const bad of [undefined, '', 'YES', 'maybe', null, 1]) {
    assert.equal(parentSaveBlocker(ready, '9', { ...good, disable_variants: bad }), PARENT_NOT_LOADED_MESSAGE);
    assert.equal(parentSaveBlocker(ready, '9', { ...good, no_discount_banner: bad }), PARENT_NOT_LOADED_MESSAGE);
  }
  assert.equal(parentSaveBlocker(ready, '9', undefined), PARENT_NOT_LOADED_MESSAGE);
});

test('save guard: a failed load explains the failure and points to Retry', () => {
  const failed = { status: 'error', productId: '9', original: null, error: 'Network Error' };
  const message = parentSaveBlocker(failed, '9', { no_discount_banner: 'N', disable_variants: 'N' });
  assert.match(message, /could not be loaded: Network Error/);
  assert.match(message, /Retry/);
  assert.equal(parentSaveBlocker(failed, '10', { no_discount_banner: 'N', disable_variants: 'N' }), PARENT_NOT_LOADED_MESSAGE);
});

test('the save guard keeps the exact original wording', () => {
  assert.equal(PARENT_NOT_LOADED_MESSAGE, "The selected product's settings have not finished loading. Wait for them to load, or choose the product again, before saving.");
});

test('preserving Discount and Disable Variants: unchanged settings are never rewritten after loading', async () => {
  const api = fakeApi({ 7: product(7, 'Y', 'Y') });
  const loaded = await fetchParentSettings(api, 7);
  const saved = await saveVariantAndParent({ api, values: { id: 3, product_id: 7, name: 'Small' }, parentSettings: { ...loaded }, original: loaded });
  assert.deepEqual(saved, { no_discount_banner: 'Y', disable_variants: 'Y' });
  assert.ok(!api.calls.some((c) => c.method === 'PATCH' && c.url === 'products'));
});

// ---- Minimum Buying Quantity ----

test('Minimum Purchase Quantity field is a required whole-number input with min 1 and step 1', () => {
  assert.equal(MINIMUM_BUYING_QUANTITY_FIELD.key, 'minimum_buying_count');
  assert.equal(MINIMUM_BUYING_QUANTITY_FIELD.label, 'Minimum Purchase Quantity');
  assert.equal(MINIMUM_BUYING_QUANTITY_FIELD.type, 'number');
  assert.equal(MINIMUM_BUYING_QUANTITY_FIELD.min, 1);
  assert.equal(MINIMUM_BUYING_QUANTITY_FIELD.step, 1);
  assert.equal(MINIMUM_BUYING_QUANTITY_FIELD.required, true);
  assert.equal(MINIMUM_BUYING_QUANTITY_DEFAULT, '1');
});

test('Minimum Buying Quantity accepts positive whole numbers only', () => {
  for (const [input, expected] of [[1, 1], ['1', 1], [' 12 ', 12], ['007', 7], [500, 500], ['2147483647', 2147483647]]) {
    assert.deepEqual(validateMinimumBuyingQuantity(input), { value: expected }, String(input));
  }
});

test('Minimum Buying Quantity rejects zero, negative, decimal, empty and non-numeric input', () => {
  for (const bad of [0, '0', -1, '-1', 1.5, '1.5', '2.0', '', '  ', null, undefined, 'abc', '1e2', '+3', '1,000', true, NaN, Infinity, {}, [], '2147483648', '99999999999999999999']) {
    const result = validateMinimumBuyingQuantity(bad);
    assert.ok(result.error, 'should reject ' + String(bad));
    assert.ok(!('value' in result));
  }
  assert.equal(validateMinimumBuyingQuantity('0').error, MINIMUM_BUYING_QUANTITY_MESSAGE);
});

test('the saved quantity is shown when editing, and a missing API value is never replaced by a default', () => {
  assert.equal(minimumBuyingQuantityFormValue({ minimum_buying_quantity: 12 }), '12');
  assert.equal(minimumBuyingQuantityFormValue({ minimum_buying_quantity: '6' }), '6');
  assert.equal(minimumBuyingQuantityFormValue({}), '');
  assert.equal(minimumBuyingQuantityFormValue({ minimum_buying_quantity: null }), '');
  assert.equal(minimumBuyingQuantityFormValue(undefined), '');
  // an empty value then fails validation instead of silently saving 1 over a stored quantity
  assert.ok(withMinimumBuyingQuantity({ minimum_buying_quantity: minimumBuyingQuantityFormValue({}) }).error);
});

test('creating a product submits a numeric minimum_buying_quantity with the existing request', async () => {
  const api = fakeApi({});
  const prepared = withMinimumBuyingQuantity({ name: 'Tea', price: 10, no_discount_banner: 'Y', disable_variants: 'N', minimum_buying_quantity: '6' });
  assert.ok(!prepared.error);
  await api.request({ method: 'POST', url: 'products', data: prepared.values });
  const call = api.calls.at(-1);
  assert.equal(call.method, 'POST');
  assert.equal(call.url, 'products');
  assert.strictEqual(call.data.minimum_buying_quantity, 6);
  assert.equal(call.data.no_discount_banner, 'Y');
  assert.equal(call.data.disable_variants, 'N');
});

test('editing a product keeps the saved quantity and both settings in the PATCH payload', async () => {
  const row = { id: 4, name: 'Tea', no_discount_banner: 'Y', disable_variants: 'Y', minimum_buying_quantity: 12 };
  const form = { id: row.id, name: row.name, no_discount_banner: row.no_discount_banner, disable_variants: row.disable_variants, minimum_buying_quantity: minimumBuyingQuantityFormValue(row) };
  const prepared = withMinimumBuyingQuantity({ ...form, name: 'Tea (new)' });
  assert.deepEqual(prepared.values, { id: 4, name: 'Tea (new)', no_discount_banner: 'Y', disable_variants: 'Y', minimum_buying_quantity: 12, minimum_buying_count: 12 });
  assert.deepEqual(form, { id: 4, name: 'Tea', no_discount_banner: 'Y', disable_variants: 'Y', minimum_buying_quantity: '12' }, 'form state is not mutated');
});

test('an invalid quantity blocks the request and leaves the form values untouched', () => {
  const form = { name: 'Tea', price: 10, minimum_buying_quantity: '0' };
  const prepared = withMinimumBuyingQuantity(form);
  assert.equal(prepared.error, MINIMUM_BUYING_QUANTITY_MESSAGE);
  assert.ok(!prepared.values);
  assert.equal(form.minimum_buying_quantity, '0');
});

test('a backend validation error for the quantity is shown with its field name', () => {
  const err = new Error('Request failed');
  err.response = { data: { minimum_buying_quantity: 'Minimum buying quantity must be a whole number of 1 or more.' } };
  assert.equal(describeApiError(err), 'minimum_buying_quantity: Minimum buying quantity must be a whole number of 1 or more.');
});
