import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateGstNumber } from './fieldValidation.js';

const LENGTH_ERROR = 'GST Number must contain exactly 15 characters.';

test('GST Number: empty is optional', () => {
  for (const value of ['', null, undefined]) assert.equal(validateGstNumber(value), '');
  assert.equal(validateGstNumber('   '), LENGTH_ERROR);
});

test('GST Number: any 15-character value passes (numeric, alphabetic, mixed, symbols, lower case, inner spaces)', () => {
  for (const value of ['123456789012345', 'ABCDEFGHIJKLMNO', '22ABCDE1234F1Z5', 'abcdefghijklmno', '!!!!!!!!!!!!!!!', 'AB CD EF GH IJK', '00AAAAA0000A0Z0', 'ZZZZZZZZZZZZZZZ']) {
    assert.equal(value.length, 15, value);
    assert.equal(validateGstNumber(value), '', value);
  }
});

test('GST Number: whitespace is counted as entered, not trimmed or rewritten', () => {
  assert.equal(validateGstNumber('  123456789012345  '), LENGTH_ERROR);
  assert.equal(validateGstNumber(' 12345678901234'), '');
});

test('GST Number: 14 and 16 characters (and anything else non-empty) fail with the length message only', () => {
  for (const value of ['12345678901234', '1234567890123456', 'X', '22ABCDE1234F1Z']) assert.equal(validateGstNumber(value), LENGTH_ERROR, value);
});

test('GST Number: length follows the input string length', () => {
  assert.equal(validateGstNumber('??'.repeat(7)), LENGTH_ERROR);
  assert.equal(validateGstNumber('??'.repeat(8)), LENGTH_ERROR);
});

test('Customers page applies the length-only rule: no GST-registered dependency and no input rewriting', () => {
  const page = readFileSync(new URL('./CustomersPage.jsx', import.meta.url), 'utf8');
  assert.ok(!/GST registered is Yes/.test(page));
  assert.ok(!/values\.gst === ["']Y["']/.test(page));
  assert.ok(!/toUpperCase\(\)\.replace\(\/\\s\/g/.test(page));
  assert.match(page, /maxLength=\{15\}/);
  assert.match(page, /validateGstNumber\(values\.gst_number\)/);
});

test('Customers page maps the length error onto the GST Number field', () => {
  const page = readFileSync(new URL('./CustomersPage.jsx', import.meta.url), 'utf8');
  assert.match(page, /\/GST Number\/i\.test\(problem\)\) errors\.gst_number = problem/);
});
