// Product-level settings shown in the product form and the product variant modal.
// They belong to the parent product, so they are only ever stored through the products
// endpoint and are never sent to the product-variants endpoint.
export const PARENT_FIELDS = ['no_discount_banner', 'disable_variants'];
export const YN_OPTIONS = [['N', 'No'], ['Y', 'Yes']];
export const PRODUCT_SETTING_FIELDS = [
  { key: 'no_discount_banner', label: 'Discount Y/N', options: YN_OPTIONS },
  { key: 'disable_variants', label: 'Disable Variants Y/N', options: YN_OPTIONS },
];

// Minimum Buying Quantity is a product-level setting stored by the backend in the existing legacy
// column zg_product.moq and exposed by the admin API as `minimum_buying_quantity`.
export const MINIMUM_BUYING_QUANTITY_KEY = 'minimum_buying_count';
export const MINIMUM_BUYING_QUANTITY_LEGACY_KEY = 'minimum_buying_quantity';
export const MINIMUM_BUYING_QUANTITY_DEFAULT = '1';
export const MINIMUM_BUYING_QUANTITY_MESSAGE = 'Minimum purchase quantity must be a positive whole number.';
const MINIMUM_BUYING_QUANTITY_MAX = 2147483647;

// Accepts positive whole numbers only (number or digit string). Rejects empty, zero, negative,
// decimal, exponent and non-numeric input. Returns { value } or { error }.
export function validateMinimumBuyingQuantity(input) {
  let number;
  if (typeof input === 'number') {
    if (!Number.isInteger(input)) return { error: MINIMUM_BUYING_QUANTITY_MESSAGE };
    number = input;
  } else if (typeof input === 'string') {
    const text = input.trim();
    if (!/^[0-9]+$/.test(text)) return { error: MINIMUM_BUYING_QUANTITY_MESSAGE };
    number = Number(text);
  } else {
    return { error: MINIMUM_BUYING_QUANTITY_MESSAGE };
  }
  if (!Number.isSafeInteger(number) || number < 1) return { error: MINIMUM_BUYING_QUANTITY_MESSAGE };
  if (number > MINIMUM_BUYING_QUANTITY_MAX) return { error: 'Minimum Buying Quantity is too large.' };
  return { value: number };
}

// Form value for an existing product row. Returns '' (not a made-up default) when the API did not
// send the field, so saving can never silently overwrite a stored value with a default.
export function minimumBuyingQuantityFormValue(row) {
  const raw = row?.[MINIMUM_BUYING_QUANTITY_KEY] ?? row?.[MINIMUM_BUYING_QUANTITY_LEGACY_KEY];
  return raw === undefined || raw === null ? '' : String(raw);
}

// Validates the form value and puts the numeric quantity into a copy of the payload.
export function withMinimumBuyingQuantity(values) {
  const checked = validateMinimumBuyingQuantity(values?.[MINIMUM_BUYING_QUANTITY_KEY] ?? values?.[MINIMUM_BUYING_QUANTITY_LEGACY_KEY]);
  if (checked.error) return { error: checked.error };
  return { values: { ...values, [MINIMUM_BUYING_QUANTITY_KEY]: checked.value, [MINIMUM_BUYING_QUANTITY_LEGACY_KEY]: checked.value } };
}

export const MINIMUM_BUYING_QUANTITY_FIELD = {
  key: MINIMUM_BUYING_QUANTITY_KEY,
  label: 'Minimum Purchase Quantity',
  type: 'number',
  required: true,
  min: 1,
  step: 1,
  help: 'Smallest quantity a customer can buy. Whole number, 1 or more.',
};

export function isYesNo(value) {
  return value === 'Y' || value === 'N';
}

// Accepts "Y"/"N" in any case or padding and returns the exact stored form; anything else stays
// unchanged so isYesNo() still rejects it.
export function normalizeYesNo(value) {
  if (typeof value !== 'string') return value;
  const normalized = value.trim().toUpperCase();
  return isYesNo(normalized) ? normalized : value;
}

function normalizeProductId(productId) {
  const text = String(productId ?? '').trim();
  if (!/^[0-9]+$/.test(text) || Number(text) <= 0) return null;
  return Number(text);
}

export const PARENT_NOT_LOADED_MESSAGE =
  "The selected product's settings have not finished loading. Wait for them to load, or choose the product again, before saving.";

export const IDLE_PARENT_STATE = Object.freeze({ status: 'idle', productId: '', original: null, error: '' });

// Returns '' when the variant may be saved, otherwise the message to show. The guard itself is
// unchanged: saving needs settings that finished loading for exactly this product and valid Y/N values.
export function parentSaveBlocker(parentState, productId, parentSettings) {
  const id = String(productId ?? '');
  if (parentState?.status === 'error' && parentState.productId === id) {
    return "The selected product's settings could not be loaded: " + parentState.error + '. Use Retry, or choose the product again, before saving.';
  }
  if (
    !parentState ||
    parentState.status !== 'ready' ||
    parentState.productId !== id ||
    PARENT_FIELDS.some((name) => !isYesNo(parentSettings?.[name]))
  ) return PARENT_NOT_LOADED_MESSAGE;
  return '';
}

export function stripParentFields(values) {
  const rest = { ...values };
  PARENT_FIELDS.forEach((name) => { delete rest[name]; });
  return rest;
}

export function describeApiError(err) {
  const body = err?.response?.data;
  if (typeof body === 'string') return body;
  if (body && typeof body === 'object') {
    return Object.entries(body)
      .map(([field, message]) => field + ': ' + (Array.isArray(message) ? message.join(', ') : typeof message === 'object' ? JSON.stringify(message) : String(message)))
      .join(' · ');
  }
  return err?.message || 'request failed';
}

// Reads the saved settings of one parent product from the products API (exact "Y"/"N" strings).
export async function fetchParentSettings(api, productId) {
  // Fail with a clear message instead of an opaque "api.get is not a function" when called wrongly.
  if (!api || typeof api.get !== 'function') throw new TypeError('fetchParentSettings(api, productId) needs the API client as its first argument.');
  const id = normalizeProductId(productId);
  if (id === null) throw new Error('Choose a valid product before loading its settings.');
  const response = await api.get('products', { params: { id, page: 1, page_size: 1 } });
  const product = response?.data?.results?.[0];
  if (!product || String(product.id) !== String(id)) throw new Error('Parent product ' + id + ' was not found.');
  const settings = {};
  PARENT_FIELDS.forEach((name) => { settings[name] = normalizeYesNo(product[name]); });
  if (PARENT_FIELDS.some((name) => !isYesNo(settings[name]))) throw new Error('The product API returned an unexpected value for its settings.');
  return settings;
}

// Loading lifecycle for the selected product's settings. Every load() supersedes the previous one:
// a response that arrives after a newer load() (or cancel()) is discarded, so a slow request for an
// earlier product can never overwrite the state of the current one. Failures end in status "error"
// (never "ready"); calling load() again is the retry.
export function createParentSettingsLoader({ api, onState }) {
  let sequence = 0;
  async function load(productId) {
    const request = ++sequence;
    const id = String(productId ?? '');
    onState({ status: 'loading', productId: id, original: null, error: '' });
    try {
      const settings = await fetchParentSettings(api, id);
      if (request === sequence) onState({ status: 'ready', productId: id, original: settings, error: '' });
    } catch (err) {
      if (request === sequence) onState({ status: 'error', productId: id, original: null, error: describeApiError(err) });
    }
  }
  function cancel() { sequence += 1; }
  function reset() { cancel(); onState({ ...IDLE_PARENT_STATE }); }
  return { load, cancel, reset };
}

// 1) saves the variant (variant fields only), 2) saves changed settings on the parent product,
// 3) re-reads the product and verifies the stored values. The two writes cannot be atomic: when
// step 2 or 3 fails the variant stays saved and the thrown error (partial: true) says so, so the
// caller can keep the form open and retry only the product settings (alreadySaved: true).
export async function saveVariantAndParent({ api, endpoint = 'product-variants', values, parentSettings, original = {}, alreadySaved = false, onVariantSaved = () => {} }) {
  const productId = Number(values.product_id);
  if (!alreadySaved) {
    await api.request({ method: values.id ? 'PATCH' : 'POST', url: endpoint, data: stripParentFields(values) });
    onVariantSaved();
  }
  try {
    const changed = PARENT_FIELDS.filter((name) => parentSettings[name] !== original?.[name]);
    if (changed.length) {
      const patch = { id: productId };
      changed.forEach((name) => { patch[name] = parentSettings[name]; });
      await api.patch('products', patch);
    }
    const saved = await fetchParentSettings(api, productId);
    const mismatch = PARENT_FIELDS.filter((name) => saved[name] !== parentSettings[name]);
    if (mismatch.length) throw new Error('the server returned different values for ' + mismatch.join(', '));
    return saved;
  } catch (err) {
    const error = new Error('The variant was saved, but the product settings were not saved or could not be verified: ' + describeApiError(err) + '. Your selections are still in the form; press Save again to retry the product settings.');
    error.partial = true;
    throw error;
  }
}
