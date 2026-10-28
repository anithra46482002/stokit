export const MIN_ADVANCE_OFFER_MONTHS = 12;
export const DEFAULT_ADVANCE_OFFER_MONTHS = 12;

export function isValidAdvanceOfferDuration(value) {
  const duration = Number(value);
  return Number.isInteger(duration) && duration >= MIN_ADVANCE_OFFER_MONTHS;
}