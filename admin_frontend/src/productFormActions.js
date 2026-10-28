// Pure helpers for the Products page Add/Edit dialog and Delete (no React, so they are unit-testable).
import { validateMinimumBuyingQuantity, withMinimumBuyingQuantity } from './productSettings.js';
import { errorText } from './uiUtils.js';
import { apiErrorText } from './variantActions.js';

const NUMERIC = ['price', 'mrp', 'discount', 'category_id'];

export function buildProductPayload(editing) {
  const isEdit = Boolean(editing?.id);
  const values = { ...editing };
  delete values.color; // preserve the legacy color when editing unrelated fields
  delete values.discount_banners; // banner paths are sent through their own request
  delete values.image_url; // display-only
  const quantity = withMinimumBuyingQuantity(values);
  if (quantity.error) return { error: quantity.error };
  values.minimum_buying_count = quantity.values.minimum_buying_count;
  values.minimum_buying_quantity = quantity.values.minimum_buying_quantity;
  // Product-level GST amount/percentage are configured on variants, not in this product form.
  // Omit these keys so PATCH never overwrites legacy values with default zeroes.
  delete values.gst_percentage;
  delete values.gst_price;
  values.keywords = String(values.keywords || '').slice(0, 255);
  try {
    values.set_contains = JSON.parse(String(values.set_contains || '[]'));
    if (values.set_contains === null || typeof values.set_contains !== 'object') throw new Error('bad');
  } catch {
    return { error: 'Set contains must be a valid JSON array or object.' };
  }
  if (!String(values.name || '').trim()) return { error: 'Product name is required.' };
  // The Add form omits MRP; the API needs a valid value.
  if (values.mrp === '' || values.mrp == null) values.mrp = values.price;
  // The API refuses an empty code on edit, so a legacy product without one is saved without touching it.
  if (isEdit && !String(values.code ?? '').trim()) delete values.code;
  else if (values.code == null) values.code = '';
  for (const key of NUMERIC) {
    if (values[key] === '' || values[key] == null) continue;
    values[key] = Number(values[key]);
    if (!Number.isFinite(values[key]) || (key !== 'category_id' && values[key] < 0)) return { error: 'Enter a valid ' + key.replace('_', ' ') + '.' };
  }
  if (values.price === '' || values.price == null) return { error: 'Price is required.' };
  values.subcategory_id = values.subcategory_id ? Number(values.subcategory_id) : null;
  return { values };
}

// One variant row -> API body. Returns { payload } or { error }. Blank-name rows are skipped by the caller.
export function buildVariantPayload(variant, productId) {
  const name = String(variant?.name || '').trim();
  const payload = { product_id: Number(productId), name, price: Number(variant?.price || 0), mrp: Number(variant?.mrp || variant?.price || 0), quantity: Number(variant?.quantity || 0), discount: String(variant?.discount || '0'), gst: variant?.gst || 'N', gst_price: Number(variant?.gst_price || 0) };
  const minimum = validateMinimumBuyingQuantity(String(variant?.minimum_buying_count ?? '1'));
  if (minimum.error) return { error: 'Variant ' + name + ': ' + minimum.error };
  payload.minimum_buying_count = minimum.value;
  if (![payload.price, payload.mrp, payload.quantity, payload.gst_price].every(Number.isFinite) || payload.price < 0 || payload.mrp < 0 || payload.quantity < 0 || payload.gst_price < 0) {
    return { error: 'Variant ' + name + ': enter valid non-negative price, MRP, quantity and GST amount.' };
  }
  return { payload };
}

const signature = (payload) => JSON.stringify({ ...payload, product_id: 0 });

export function newSaveProgress() { return { productId: null, bannerPaths: [], bannersDone: false, imagesDone: 0, imagePaths: [] }; }

// Runs the multi-request save. `progress` is mutated as each request succeeds and is passed back in on a
// retry, so a failure half-way (e.g. a variant rejected after the product was stored) never duplicates the
// product, a variant, an uploaded banner or an image. Unchanged variants are not written at all.
export async function saveProductForm(api, upload, { values, bannerFiles = [], removedBannerPaths = [], oldBannerPaths = [], productImageFiles = [], progress }) {
  const existingId = values.id || progress.productId;
  const response = await api.request({ method: existingId ? 'PATCH' : 'POST', url: 'products', data: existingId ? { ...values, id: existingId } : values });
  const productId = existingId || response?.data?.id;
  if (!productId) throw new Error('The server did not confirm the product ID.');
  progress.productId = productId;

  if (!progress.bannersDone && (bannerFiles.length > 0 || removedBannerPaths.length > 0)) {
    for (let i = progress.bannerPaths.length; i < bannerFiles.length; i += 1) {
      const uploaded = await upload(bannerFiles[i]);
      if (!uploaded?.image_path) throw new Error('Image upload response is missing image_path.');
      progress.bannerPaths.push(uploaded.image_path);
    }
    const paths = oldBannerPaths.filter((path) => !removedBannerPaths.includes(path)).concat(progress.bannerPaths);
    if (paths.length > 10) throw new Error('A product can have at most 10 discount banners.');
    await api.patch('products', { id: Number(productId), discount_banners: paths });
    progress.bannersDone = true;
  }
  for (; progress.imagesDone < productImageFiles.length;) {
    const index = progress.imagesDone;
    if (!progress.imagePaths[index]) {
      const uploaded = await upload(productImageFiles[index]);
      if (!uploaded?.image_path) throw new Error('Image upload response is missing image_path.');
      progress.imagePaths[index] = uploaded.image_path;
    }
    await api.post('product-images', { product_id: Number(productId), image_path: progress.imagePaths[index], main: index === 0 });
    progress.imagesDone += 1;
  }
  return { productId };
}

// Honest message when the save stopped half-way.
export function describeSaveFailure(err, progress, wasNew) {
  const base = err?.response ? errorText(err) : (err?.message || 'The server could not be reached');
  const savedVariants = 0;
  if (!progress?.productId) return base + ' Nothing was saved.';
  const stored = wasNew ? 'The product was created' : 'The product changes were saved';
  return base + ' ' + stored + ' but the rest was not. Fix the problem and press Save again to finish; nothing will be duplicated.';
}

// Product delete failure -> { message, archivable, gone }. 409 = protected record (offer Hide instead).
export function describeProductDeleteError(err, label) {
  const status = err?.response?.status;
  if (!err?.response) return { message: `"${label}" was not deleted: ${err?.message || 'the server could not be reached'}. Nothing was removed; check the connection and try again.`, archivable: false, gone: false };
  const detail = apiErrorText(err);
  if (status === 409) return { message: `"${label}" was not deleted: ${detail} Nothing was changed.`, archivable: true, gone: false };
  if (status === 404) return { message: `"${label}" no longer exists (it may already have been deleted). The list has been refreshed.`, archivable: false, gone: true };
  if (status === 401 || status === 403) return { message: `"${label}" was not deleted: you do not have permission for this action (${detail}).`, archivable: false, gone: false };
  if (status >= 500) return { message: `"${label}" was not deleted because of a server error. Nothing was removed. ${detail}`, archivable: false, gone: false };
  return { message: `"${label}" was not deleted: ${detail}`, archivable: false, gone: false };
}
