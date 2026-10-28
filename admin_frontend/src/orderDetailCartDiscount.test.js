import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('./OrderDetailPage.jsx', import.meta.url), 'utf8');

test('order details never present the cart promotion as a percentage', () => {
  assert.ok(!/cart_discount_percent/.test(page), 'the page no longer reads or prints a cart discount percentage');
  assert.ok(!/cart discount ' \+ detail\.items/.test(page) && !/% \(/.test(page), 'the old "cart discount N% (amount)" footer is gone');
  assert.match(page, /fixed cart discount/);
});

test('order details show the backend fixed discount amount and the recorded figures', () => {
  assert.match(page, /detail\.items\.cart_discount_type === 'fixed'/);
  assert.match(page, /money\(f\.cart_discount\)/);
  assert.match(page, /Subtotal after cart discount/);
  assert.match(page, /Recorded order amount \(derived payable amount[^<]*\{money\(f\.recorded_order_amount\)\}/);
  assert.doesNotMatch(page, /Stored subtotal after cart discount:|GST is calculated with the current GST rules because this database stores no per-order GST snapshot/);
  assert.match(page, /f\.payable_reliably_derived/);
  assert.match(page, /money\(f\.amount_payable \?\? f\.grand_total\)/);
});

test('order details tell the admin that bonus balances are current, not historical', () => {
  assert.match(page, /not the balance on the day this order was placed/);
  assert.match(page, /recorded_total_notice/);
});

const list = readFileSync(new URL('./OrdersPage.jsx', import.meta.url), 'utf8');

test('All Orders shows the derived payable amount and falls back to an honestly labelled subtotal', () => {
  assert.match(list, /<th>Amount Payable<\/th>/);
  assert.doesNotMatch(list, /<th>Total Amount<\/th>/);
  assert.match(list, /money\(o\.payable_amount \?\? o\.total_amount\)/);
  assert.match(list, /\(subtotal\)/);
});

test('order details only call the stored subtotal the recorded amount with an explicit fallback label', () => {
  assert.doesNotMatch(page, /Recorded order total/);
  assert.match(page, /cannot be reconstructed reliably/);
});
