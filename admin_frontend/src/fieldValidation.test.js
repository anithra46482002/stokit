import test from 'node:test';
import assert from 'node:assert/strict';
import { validateEmail, validateMobile, normalizeIndianMobile } from './fieldValidation.js';

test('email validation accepts Gmail and business addresses and trims whitespace', () => {
  assert.equal(validateEmail('  user@gmail.com  '), '');
  assert.equal(validateEmail('person@company.co.in'), '');
  assert.notEqual(validateEmail('bad@@gmail.com'), '');
  assert.notEqual(validateEmail('user@domain'), '');
  assert.notEqual(validateEmail('a..b@gmail.com'), '');
  assert.equal(validateEmail('', { required: false }), '');
  assert.notEqual(validateEmail(''), '');
});

test('Indian mobile validation accepts supported formats and rejects invalid numbers', () => {
  assert.equal(validateMobile('9876543210'), '');
  assert.equal(validateMobile('+91 98765-43210'), '');
  assert.equal(validateMobile('09876543210'), '');
  assert.equal(normalizeIndianMobile('+919876543210'), '9876543210');
  for (const value of ['1234567890', '987654321', '98765432100', '98765abc10', '+1 202 555 0100']) assert.notEqual(validateMobile(value), '', value);
  assert.equal(validateMobile('', { required: false }), '');
  assert.notEqual(validateMobile('', { required: true }), '');
});