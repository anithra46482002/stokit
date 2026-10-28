import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_ADVANCE_OFFER_MONTHS, MIN_ADVANCE_OFFER_MONTHS, isValidAdvanceOfferDuration } from './advanceOfferValidation.js';

test('new advance offers default to 12 months', () => {
  assert.equal(DEFAULT_ADVANCE_OFFER_MONTHS, 12);
  assert.equal(MIN_ADVANCE_OFFER_MONTHS, 12);
});

test('frontend duration validation rejects 11 months and invalid values', () => {
  for (const value of [11, 0, -1, 11.5, 12.5, '', 'abc', null]) {
    assert.equal(isValidAdvanceOfferDuration(value), false, String(value));
  }
});

test('frontend duration validation accepts 12, 13, 18 and 24 months', () => {
  for (const value of [12, 13, 18, 24]) assert.equal(isValidAdvanceOfferDuration(value), true);
});