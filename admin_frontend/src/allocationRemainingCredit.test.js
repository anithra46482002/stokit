import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('./ManageAllocationsPage.jsx', import.meta.url), 'utf8');

test('allocation table shows the backend remaining balance, not the original monthly allowance', () => {
  assert.match(page, /"Remaining Credit — " \+ periodLabel/);
  assert.match(page, /<td>\{money\(r\.remaining_this_month\)\}<\/td>/);
  assert.match(page, /<td>\{money\(r\.carry_forward\)\}<\/td>/);
  assert.ok(!/remaining_this_month\s*\?\?\s*r\.monthly_credit_release/.test(page), 'no fallback to the allowance');
  assert.ok(!/nothing is carried forward/i.test(page), 'the note no longer claims credit expires');
});
