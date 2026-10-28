// Shared image URL helpers for the admin UI. Pure functions (no import.meta / DOM) so they are unit-testable.
// The API already returns absolute `image_url`s; this only normalises what a component is about to put in <img src>.

const ABSOLUTE = /^https?:\/\//i;
const PREVIEW = /^(blob:|data:image\/)/i;
const PREFIXES = ['admin/manage/', 'manage/'];

// "http://127.0.0.1:8000/admin-api/" -> "http://127.0.0.1:8000/admin/manage/"
export function mediaBaseFromApiBase(apiBase) {
  try {
    return new URL(apiBase).origin + '/admin/manage/';
  } catch {
    return '';
  }
}

function encodeParts(path) {
  return path.split('/').map((part) => encodeURIComponent(part)).join('/');
}

// Returns a usable URL string, or '' when there is nothing safe to display.
export function resolveImageUrl(value, mediaBase = '') {
  if (typeof value !== 'string') return '';
  let v = value.trim().replace(/\\/g, '/');
  if (!v || /^[a-zA-Z]:\//.test(v) || /^file:/i.test(v)) return '';
  if (PREVIEW.test(v)) return v;
  if (v.startsWith('//')) v = 'https:' + v;
  if (ABSOLUTE.test(v)) return v.replace(/ /g, '%20'); // never touch host/path otherwise
  v = v.replace(/^\/+/, '');
  for (let changed = true; changed;) {
    changed = false;
    for (const p of PREFIXES) {
      if (v.startsWith(p)) { v = v.slice(p.length).replace(/^\/+/, ''); changed = true; }
    }
  }
  const parts = v.split('/').filter(Boolean);
  if (!parts.length || parts.includes('..') || parts.includes('.') || !mediaBase) return '';
  let decoded;
  try { decoded = parts.map(decodeURIComponent).join('/'); } catch { decoded = parts.join('/'); }
  return mediaBase.replace(/\/+$/, '') + '/' + encodeParts(decoded);
}

export function isUsableImageUrl(value) {
  return ABSOLUTE.test(value || '') || PREVIEW.test(value || '');
}

// Decides what <SafeImage> renders. A URL that already failed is never retried (no infinite error loops);
// a new `src` (after an upload/edit) resolves to a new URL and is tried once.
export function imageDisplayState(src, failedUrl, mediaBase = '') {
  const url = resolveImageUrl(src, mediaBase);
  if (!url) return { kind: 'fallback', url: '' };
  if (failedUrl === url) return { kind: 'fallback', url };
  return { kind: 'image', url };
}
