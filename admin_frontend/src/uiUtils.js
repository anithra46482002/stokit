export function errorText(err) {
  const data = err.response?.data;
  if (!data) return err.message || 'Request failed';
  if (typeof data === 'string') {
    // Django/proxy error pages may be returned as HTML; never render their markup as a user-facing message.
    if (/<\/?(html|!doctype|head|body|title|pre)\b/i.test(data) || /<[^>]+>/.test(data)) {
      const status = err.response?.status;
      if (status === 401) return 'Your session has expired. Please sign in again.';
      if (status === 403) return 'You do not have permission to complete this request.';
      if (status === 404) return 'The requested resource was not found.';
      if (status >= 500) return 'The server could not complete the request. Please try again later.';
      return 'The request failed. Please check your input and try again.';
    }
    return data;
  }
  const describe = (value) => {
    if (Array.isArray(value)) return value.map(describe).filter(Boolean).join(', ');
    if (value && typeof value === 'object') return Object.entries(value).map(([key, child]) => key + ': ' + describe(child)).filter(Boolean).join(', ');
    return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
  };
  const fieldErrors = data.errors && typeof data.errors === 'object'
    ? Object.entries(data.errors).map(([field, message]) => field + ': ' + describe(message)).filter(Boolean).join(' ')
    : '';
  return [data.detail, data.message, fieldErrors,
    ...Object.entries(data).filter(([key]) => key !== 'errors' && key !== 'detail' && key !== 'message').map(([key, value]) => {
      const message = describe(value);
      return message ? key + ': ' + message : '';
    })]
    .filter(Boolean).join(' ') || 'Request failed';
}

export async function fetchAll(api, endpoint, params) {
  const pageSize = 100;
  const maxPages = 1000;
  const rows = [];
  const seenFullPages = new Set();
  let page = 1;
  let expectedCount = null;

  while (true) {
    if (page > maxPages) {
      throw new Error(`Pagination exceeded ${maxPages} pages; refusing to return incomplete results.`);
    }
    const response = await api.get(endpoint, {
      params: Object.assign({}, params || {}, { page, page_size: pageSize }),
    });
    const data = response.data;
    const batch = Array.isArray(data?.results) ? data.results : [];
    if (Number.isFinite(data?.count) && data.count >= 0) expectedCount = data.count;

    if (batch.length === 0) {
      if (expectedCount !== null && rows.length < expectedCount) {
        throw new Error(`Pagination ended at page ${page} after ${rows.length} of ${expectedCount} reported records.`);
      }
      break;
    }

    if (batch.length === pageSize) {
      const signature = JSON.stringify(batch);
      if (seenFullPages.has(signature)) {
        throw new Error(`Pagination repeated a full page at page ${page}; refusing to return incomplete results.`);
      }
      seenFullPages.add(signature);
    }

    rows.push(...batch);
    if (expectedCount !== null && rows.length >= expectedCount) break;
    if (batch.length < pageSize) {
      if (expectedCount !== null && rows.length < expectedCount) {
        throw new Error(`Pagination stopped at a short page after ${rows.length} of ${expectedCount} reported records.`);
      }
      break;
    }
    page += 1;
  }

  return rows;
}

export function targetCategoryOptions(categories) {
  return (Array.isArray(categories) ? categories : [])
    .filter((category) => normalizeTargetCategoryId(category?.id) !== null)
    .map((category) => [String(normalizeTargetCategoryId(category.id)), String(category.name || "")]);
}

export function normalizeTargetCategoryId(value) {
  if (typeof value === 'boolean' || value == null) return null;
  const text = String(value).trim();
  if (!/^[1-9][0-9]*$/.test(text)) return null;
  const id = Number(text);
  return Number.isSafeInteger(id) ? id : null;
}

export function validateRewardImageFile(file) {
  if (!file) return "Choose an image file.";
  if (file.size > 5 * 1024 * 1024) return "Image must be 5 MB or smaller.";
  const allowedTypes = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);
  const extension = (file.name || "").split(".").pop().toLowerCase();
  const allowedExtensions = new Set(["jpg", "jpeg", "png", "gif", "webp"]);
  if (!allowedTypes.has(file.type) && !allowedExtensions.has(extension)) {
    return "Choose a JPG, PNG, GIF or WEBP image.";
  }
  return "";
}
