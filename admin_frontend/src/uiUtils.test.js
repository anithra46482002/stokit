import test from 'node:test';
import assert from 'node:assert/strict';
import { errorText, fetchAll, normalizeTargetCategoryId, targetCategoryOptions, validateRewardImageFile } from './uiUtils.js';

test('errorText includes backend field validation errors', () => {
  const message = errorText({ response: { data: {
    detail: 'Please correct the highlighted fields.',
    errors: { email: 'Invalid email address.', phone: 'Invalid phone number.' },
  } } });
  assert.match(message, /email: Invalid email address\./);
  assert.match(message, /phone: Invalid phone number\./);
});

test('errorText keeps permission and not-found messages readable', () => {
  assert.equal(errorText({ response: { data: { detail: 'Customer not found' } } }), 'Customer not found');
  assert.equal(errorText({ response: { data: { detail: 'Forbidden', code: 'denied' } } }), 'Forbidden code: denied');
});

test('fetchAll follows pagination until the backend count is satisfied', async () => {
  const calls = [];
  const api = {
    async get(endpoint, options) {
      calls.push({ endpoint, params: options.params });
      const page = options.params.page;
      if (page === 1) {
        return { data: { count: 101, page: 1, page_size: 100, results: Array.from({ length: 100 }, (_, i) => i) } };
      }
      return { data: { count: 101, page: 2, page_size: 100, results: [100] } };
    },
  };

  const rows = await fetchAll(api, 'customers', { status: 'ACTIVE' });

  assert.equal(rows.length, 101);
  assert.deepEqual(rows, Array.from({ length: 101 }, (_, i) => i));
  assert.deepEqual(calls.map((call) => call.params.page), [1, 2]);
  assert.ok(calls.every((call) => call.endpoint === 'customers' && call.params.status === 'ACTIVE' && call.params.page_size === 100));
});

test('fetchAll stops on a short page even if count metadata is absent', async () => {
  let calls = 0;
  const api = {
    async get() {
      calls += 1;
      return { data: { results: ['one'] } };
    },
  };

  assert.deepEqual(await fetchAll(api, 'categories'), ['one']);
  assert.equal(calls, 1);
});

test("fetchAll stops after an empty page when count metadata is absent", async () => {
  let calls = 0;
  const api = {
    async get() {
      calls += 1;
      return { data: { results: calls === 1 ? Array.from({ length: 100 }, (_, i) => i) : [] } };
    },
  };

  assert.equal((await fetchAll(api, "products")).length, 100);
  assert.equal(calls, 2);
});

test("fetchAll rejects repeated full pages instead of looping when pagination is ignored", async () => {
  let calls = 0;
  const repeated = Array.from({ length: 100 }, (_, i) => ({ id: i + 1 }));
  const api = { async get() { calls += 1; return { data: { count: 250, results: repeated } }; } };

  await assert.rejects(fetchAll(api, "products"), /repeated a full page at page 2/);
  assert.equal(calls, 2);
});

test("fetchAll rejects an empty page before the reported count is reached", async () => {
  const api = { async get() { return { data: { count: 150, results: [] } }; } };
  await assert.rejects(fetchAll(api, "products"), /after 0 of 150 reported records/);
});

test("fetchAll rejects a short page when count metadata says records are still missing", async () => {
  const api = { async get(endpoint, options) {
    return { data: { count: 150, results: options.params.page === 1 ? Array.from({ length: 100 }, (_, i) => i) : [100] } };
  } };
  await assert.rejects(fetchAll(api, "products"), /short page after 101 of 150 reported records/);
});

test("fetchAll paginates full pages without count metadata until a short page", async () => {
  let calls = 0;
  const api = { async get(endpoint, options) {
    calls += 1;
    return { data: { results: options.params.page === 1 ? Array.from({ length: 100 }, (_, i) => i) : [100] } };
  } };
  assert.equal((await fetchAll(api, "products")).length, 101);
  assert.equal(calls, 2);
});

test("fetchAll enforces a finite page cap when every page is full and unique", async () => {
  let calls = 0;
  const api = {
    async get(endpoint, options) {
      calls += 1;
      return { data: { results: Array.from({ length: 100 }, (_, i) => options.params.page + "-" + i) } };
    },
  };

  await assert.rejects(fetchAll(api, "products"), /Pagination exceeded 1000 pages/);
  assert.equal(calls, 1000);
});

test("fetchAll rejects repeated full pages even when count metadata is absent", async () => {
  let calls = 0;
  const repeated = Array.from({ length: 100 }, (_, i) => ({ id: i + 1 }));
  const api = { async get() { calls += 1; return { data: { results: repeated } }; } };

  await assert.rejects(fetchAll(api, "products"), /repeated a full page at page 2/);
  assert.equal(calls, 2);
});

test("Target Scheme category options submit IDs rather than display names", () => {
  assert.deepEqual(targetCategoryOptions([{ id: 7, name: "Office Supplies" }, { id: "12", name: "Books" }]), [
    ["7", "Office Supplies"],
    ["12", "Books"],
  ]);
});

test("Target Scheme category ID normalization accepts only positive integer IDs", () => {
  assert.equal(normalizeTargetCategoryId("7"), 7);
  assert.equal(normalizeTargetCategoryId(12), 12);
  for (const invalid of ["Office Supplies", "", "  ", "7.0", "0", "-1", true, 7.5, null, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(normalizeTargetCategoryId(invalid), null, String(invalid));
  }
});

test("Reward image upload validates allowed image types and size", () => {
  assert.equal(validateRewardImageFile({ name: "reward.webp", type: "image/webp", size: 1024 }), "");
  assert.equal(validateRewardImageFile({ name: "reward.jpg", type: "", size: 1024 }), "");
  assert.match(validateRewardImageFile({ name: "payload.txt", type: "text/plain", size: 1024 }), /JPG, PNG, GIF or WEBP/);
  assert.match(validateRewardImageFile({ name: "large.png", type: "image/png", size: 5 * 1024 * 1024 + 1 }), /5 MB or smaller/);
});

test('errorText renders array and nested backend validation details', () => {
  const message = errorText({ response: { data: {
    items: ['Quantity must be positive.', 'Duplicate product line.'],
    errors: { email: ['Enter a valid e-mail address.'] },
  } } });
  assert.match(message, /items: Quantity must be positive\., Duplicate product line\./);
  assert.match(message, /email: Enter a valid e-mail address\./);
});

test('errorText sanitizes HTML server error pages without exposing markup or tracebacks', () => {
  const message = errorText({ response: { status: 500, data: '<!doctype html><html><body><pre>secret traceback</pre></body></html>' } });
  assert.equal(message, 'The server could not complete the request. Please try again later.');
  assert.doesNotMatch(message, /<html|traceback|secret/i);
});

test('errorText handles empty and network responses safely', () => {
  assert.equal(errorText({ response: { status: 500, data: '' }, message: 'Request failed' }), 'Request failed');
  assert.equal(errorText({ message: 'Network Error' }), 'Network Error');
});
