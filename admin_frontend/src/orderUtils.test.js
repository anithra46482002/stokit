import test from 'node:test';
import assert from 'node:assert/strict';
import { validateOrderLines } from './orderUtils.js';

test('order line validation rejects missing items and invalid quantities', () => {
  assert.match(validateOrderLines([]), /at least one order item/i);
  assert.match(validateOrderLines([{ product_id: '', quantity: 1 }]), /choose a product/i);
  assert.match(validateOrderLines([{ product_id: 2, quantity: 1.5 }]), /whole-number quantity/i);
});

test('order line validation rejects duplicate products before POST', () => {
  assert.match(validateOrderLines([
    { product_id: 2, quantity: 1 },
    { product_id: '2', quantity: 3 },
  ]), /only once/i);
  assert.equal(validateOrderLines([{ product_id: 2, quantity: 4 }, { product_id: 3, quantity: 1 }]), '');
});

test('variant products require a valid variant and allow distinct variant lines', () => {
  const products = [{ id: 2, name: 'Shirt', price: '10.00', variants: [
    { id: 21, name: 'Small', price: '12.00' },
    { id: 22, name: 'Large', price: '14.00' },
  ] }];
  assert.match(validateOrderLines([{ product_id: 2, quantity: 1 }], products), /choose a variant/i);
  assert.match(validateOrderLines([{ product_id: 2, variant_id: 99, quantity: 1 }], products), /valid variant/i);
  assert.match(validateOrderLines([{ product_id: 2, variant_id: 21, quantity: 1 }, { product_id: 2, variant_id: 21, quantity: 2 }], products), /only once/i);
  assert.equal(validateOrderLines([{ product_id: 2, variant_id: 21, quantity: 1 }, { product_id: 2, variant_id: 22, quantity: 2 }], products), '');
});
