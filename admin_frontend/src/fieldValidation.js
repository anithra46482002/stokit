const EMAIL_PATTERN = /^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$/i;
export function validateEmail(value, { required = true } = {}) {
  const email = String(value ?? '').trim();
  if (!email) return required ? 'Email address is required.' : '';
  if (email.length > 254 || email.includes('..') || !EMAIL_PATTERN.test(email)) return 'Enter a valid email address, such as name@gmail.com.';
  const [local] = email.split('@');
  if (local.length > 64 || local.startsWith('.') || local.endsWith('.')) return 'Enter a valid email address, such as name@gmail.com.';
  return '';
}
export function normalizeIndianMobile(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  if (!/^[+0-9()\s-]+$/.test(raw)) return null;
  let digits = raw.replace(/\D/g, '');
  if (digits.startsWith('91') && (raw.startsWith('+91') || digits.length === 12)) digits = digits.slice(2);
  if (digits.length === 11 && digits.startsWith('0')) digits = digits.slice(1);
  if (!/^[6-9]\d{9}$/.test(digits)) return null;
  return digits;
}
export function validateMobile(value, { required = false } = {}) {
  const raw = String(value ?? '').trim();
  if (!raw) return required ? 'Mobile number is required.' : '';
  if (normalizeIndianMobile(raw) === null) return 'Enter a valid 10-digit Indian mobile number, optionally with +91.';
  return '';
}
export function normalizeEmail(value) { return String(value ?? '').trim(); }
export const GST_NUMBER_LENGTH = 15;
export function validateGstNumber(value) {
  const raw = String(value ?? "");
  return raw.length > 0 && raw.length !== GST_NUMBER_LENGTH ? "GST Number must contain exactly 15 characters." : "";
}
