import test from 'node:test';
import assert from 'node:assert/strict';
import { money, statusClass, allowedStatusOptions, formatDateTime } from '../src/orderUtils.js';

test('money formats Indian rupees with grouping and two decimals', () => {
  assert.equal(money('9530.52'), '\u20B99,530.52');
  assert.equal(money(545261.42), '\u20B95,45,261.42');
  assert.equal(money(null), '\u20B90.00');
});

test('statusClass maps legacy and Flutter statuses case-insensitively', () => {
  assert.match(statusClass('Placed'), /green/);
  assert.match(statusClass('processing'), /blue/);
  assert.match(statusClass('Cancelled'), /red/);
  assert.match(statusClass('pending'), /amber/);
  assert.equal(statusClass('mystery'), 'ord-pill');
});

test('role limits mirror the backend; admins see everything', () => {
  const options = [{ value: 'processing' }, { value: 'delivered' }, { value: 'failed' }, { value: 'cancelled' }];
  assert.deepEqual(allowedStatusOptions(options, 'DELIVERY_BOY').map((o) => o.value), ['delivered', 'failed']);
  assert.deepEqual(allowedStatusOptions(options, 'SALESMAN').map((o) => o.value), ['processing']);
  assert.equal(allowedStatusOptions(options, 'ADMIN').length, 4);
});

test('formatDateTime handles empty and invalid input', () => {
  assert.equal(formatDateTime(''), '\u2014');
  assert.equal(formatDateTime('not a date'), 'not a date');
  assert.match(formatDateTime('2026-09-28T11:03:45'), /Sep 28, 2026/);
});
