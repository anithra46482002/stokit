// Real-browser check of the Product Variants Delete button, with the Django API replaced by an in-browser mock
// (Playwright route interception). It clicks the real button on the real running admin UI and asserts what a human
// would see. It needs no password and never touches the database.
//
//   npm i playwright-core --prefix <any temp dir>          (not a project dependency)
//   set PLAYWRIGHT_CORE=<temp dir>\node_modules\playwright-core\index.mjs
//   npm run dev   (http://127.0.0.1:5173)   then:   node e2e/variant-delete.e2e.mjs
import { pathToFileURL } from 'node:url';
import fs from 'node:fs';

const core = process.env.PLAYWRIGHT_CORE;
if (!core) { console.error('Set PLAYWRIGHT_CORE to playwright-core/index.mjs'); process.exit(2); }
const { chromium } = await import(pathToFileURL(core).href);
const BASE = process.env.ADMIN_URL || 'http://127.0.0.1:5173';
const EXE = ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe'].find((p) => fs.existsSync(p));
const results = [];
const check = (label, ok, detail = '') => { results.push(ok); console.log((ok ? 'PASS  ' : 'FAIL  ') + label + (detail ? '  -> ' + detail : '')); };

const row = (id, name, extra = {}) => ({ id, product_id: 3, name, price: '10.00', mrp: '10.00', quantity: 5, discount: '0', gst: 'N', gst_price: '0.00', minimum_buying_count: 1, in_use: '', ...extra });

async function scenario(browser, title, { rows, deleteMode = 'ok', confirm = true, delayMs = 0 }, run) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    sessionStorage.setItem('stokit_admin_token', 'e2e-fake-token');
    sessionStorage.setItem('stokit_admin_user', JSON.stringify({ id: 1, role: 'SUPER_ADMIN', username: 'e2e' }));
  });
  const state = { rows: rows.map((r) => ({ ...r })), deletes: [], lists: [], dialogs: [] };
  await page.route('**/admin-api/**', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace(/^.*\/admin-api\//, '').replace(/\/$/, '');
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }, body: JSON.stringify(body) });
    if (req.method() === 'OPTIONS') return json(200, {});
    if (path === 'product-variants' && req.method() === 'GET') {
      const pageNo = Number(url.searchParams.get('page') || 1);
      state.lists.push(pageNo);
      return json(200, { count: state.rows.length, page: pageNo, page_size: 20, results: state.rows.slice((pageNo - 1) * 20, pageNo * 20) });
    }
    if (path === 'product-variants' && req.method() === 'DELETE') {
      const id = Number(url.searchParams.get('id'));
      state.deletes.push({ id, auth: req.headers()['authorization'] });
      if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
      if (deleteMode === 'abort') return route.abort('connectionrefused');
      if (deleteMode === 'ok') { state.rows = state.rows.filter((r) => r.id !== id); return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': '*' } }); }
      if (deleteMode === 'gone') { state.rows = state.rows.filter((r) => r.id !== id); return json(404, { detail: 'Variant not found' }); }
      const map = { 409: { detail: 'Variant is referenced by order history and cannot be deleted' }, 403: { detail: 'An active administrator role assignment is required for this operation.' }, 500: { detail: 'Variant could not be deleted. Nothing was removed; check the Django server log for the underlying database error.' } };
      return json(Number(deleteMode), map[deleteMode]);
    }
    return json(200, { count: 0, page: 1, page_size: 20, results: [] });
  });
  page.on('dialog', async (d) => { state.dialogs.push(d.message()); await (confirm ? d.accept() : d.dismiss()); });
  console.log('\n# ' + title);
  await page.goto(BASE + '/variants');
  await page.getByRole('table').waitFor({ timeout: 10000 });
  await run(page, state);
  await ctx.close();
}
const deleteButton = (page, name) => page.locator('tr', { hasText: name }).getByRole('button', { name: 'Delete' });
const visible = (page, name) => page.locator('tr', { hasText: name }).count().then((n) => n > 0);

const browser = await chromium.launch({ executablePath: EXE, headless: true });
try {
  await scenario(browser, 'protected variant (order history): clear message, no request, row stays', { rows: [row(2, 'Box', { in_use: 'order history' }), row(8, 'Free pen')] }, async (page, s) => {
    await deleteButton(page, 'Box').click();
    const alert = page.getByRole('alert');
    await alert.waitFor();
    const text = await alert.innerText();
    check('explanation names the variant and product IDs', /Box \(variant ID 2, product ID 3\)/.test(text), text);
    check('explanation says why (order history) and that nothing changed', /order history/.test(text) && /nothing was changed/i.test(text));
    check('no confirm dialog and no DELETE request were made', s.dialogs.length === 0 && s.deletes.length === 0);
    check('the protected row is still visible', await visible(page, 'Box'));
  });

  await scenario(browser, 'eligible variant: confirm names ID, authenticated DELETE, success message, row gone', { rows: [row(2, 'Box', { in_use: 'order history' }), row(8, 'Free pen')] }, async (page, s) => {
    await deleteButton(page, 'Free pen').click();
    await page.getByRole('status').waitFor();
    check('confirm dialog identified the variant and its ID', s.dialogs.length === 1 && /Free pen \(variant ID 8, product ID 3\)/.test(s.dialogs[0]), s.dialogs[0]);
    check('exactly one DELETE for id 8 with the bearer token', s.deletes.length === 1 && s.deletes[0].id === 8 && s.deletes[0].auth === 'Bearer e2e-fake-token', JSON.stringify(s.deletes));
    check('visible success message', /Deleted Free pen \(variant ID 8/.test(await page.getByRole('status').innerText()));
    check('row gone after the server confirmed, protected row untouched', !(await visible(page, 'Free pen')) && (await visible(page, 'Box')));
    check('list was refreshed from the server', s.lists.length >= 2);
  });

  await scenario(browser, 'cancelled confirmation sends nothing', { rows: [row(8, 'Free pen')], confirm: false }, async (page, s) => {
    await deleteButton(page, 'Free pen').click();
    await page.waitForTimeout(300);
    check('no request after cancel and row still visible', s.dialogs.length === 1 && s.deletes.length === 0 && (await visible(page, 'Free pen')));
  });

  for (const [mode, expectText, label] of [[409, /cannot be deleted: it is referenced by order history/, 'server 409 (direct/stale)'], [403, /permission/, 'permission 403'], [500, /server error. Nothing was removed/, 'server 500'], ['abort', /Nothing was removed/, 'network failure']]) {
    await scenario(browser, 'error: ' + label + ' -> visible error, row stays', { rows: [row(8, 'Free pen')], deleteMode: mode }, async (page) => {
      await deleteButton(page, 'Free pen').click();
      await page.getByRole('alert').waitFor();
      await page.waitForTimeout(400);                                  // a later list refresh must not wipe it
      check('error is visible and explains the failure', expectText.test(await page.getByRole('alert').innerText()), await page.getByRole('alert').innerText());
      check('no success message shown', (await page.getByRole('status').count()) === 0);
      check('row remains visible', await visible(page, 'Free pen'));
    });
  }

  await scenario(browser, 'not found (already deleted elsewhere): explained, list refreshed', { rows: [row(8, 'Free pen'), row(9, 'Other')], deleteMode: 'gone' }, async (page, s) => {
    await deleteButton(page, 'Free pen').click();
    await page.getByRole('alert').waitFor();
    check('message says it no longer exists', /no longer exists/.test(await page.getByRole('alert').innerText()));
    check('error survives the refresh and the stale row is gone', !(await visible(page, 'Free pen')) && (await visible(page, 'Other')) && (await page.getByRole('alert').count()) === 1);
  });

  await scenario(browser, 'double click while the request is running sends one DELETE', { rows: [row(8, 'Free pen')], delayMs: 700 }, async (page, s) => {
    const btn = deleteButton(page, 'Free pen');
    await btn.dblclick();
    await page.getByRole('status').waitFor({ timeout: 8000 });
    check('exactly one DELETE request', s.deletes.length === 1, String(s.deletes.length));
  });

  const many = Array.from({ length: 21 }, (_, i) => row(101 + i, 'Bulk ' + (101 + i)));
  await scenario(browser, 'deleting the last row of page 2 steps back to page 1', { rows: many }, async (page, s) => {
    await page.getByRole('button', { name: 'Next' }).click();
    await page.locator('tr', { hasText: 'Bulk 121' }).waitFor();
    await deleteButton(page, 'Bulk 121').click();
    await page.getByRole('status').waitFor();
    await page.waitForFunction(() => /Page 1 of 1/.test(document.body.innerText));
    check('now on page 1 of 1 with 20 records and an empty page was never shown', /20 records/.test(await page.locator('.pagination').innerText()) && (await visible(page, 'Bulk 101')) && s.lists.at(-1) === 1, s.lists.join(','));
  });
} finally {
  await browser.close();
}
const failed = results.filter((ok) => !ok).length;
console.log('\n' + results.length + ' checks, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
