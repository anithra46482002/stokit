import test from 'node:test';
import assert from 'node:assert/strict';
import { imageDisplayState, isUsableImageUrl, mediaBaseFromApiBase, resolveImageUrl } from './imageUrl.js';

const BASE = 'https://api.example/admin/manage/';

test('mediaBaseFromApiBase uses the API origin and the legacy media path', () => {
  assert.equal(mediaBaseFromApiBase('http://127.0.0.1:8000/admin-api/'), 'http://127.0.0.1:8000/admin/manage/');
  assert.equal(mediaBaseFromApiBase('not a url'), '');
});

test('absolute URLs are returned unchanged (spaces escaped, host untouched)', () => {
  assert.equal(resolveImageUrl('https://cdn.example/a/b.png?v=1', BASE), 'https://cdn.example/a/b.png?v=1');
  assert.equal(resolveImageUrl('  http://x.test/a b.png ', BASE), 'http://x.test/a%20b.png');
  assert.equal(resolveImageUrl('//cdn.example/x.png', BASE), 'https://cdn.example/x.png');
});

test('relative paths resolve against the media base without duplicating prefixes', () => {
  const want = BASE + 'uploads/x.png';
  for (const stored of ['uploads/x.png', '/uploads/x.png', '/admin/manage/uploads/x.png',
    'admin/manage/admin/manage/uploads/x.png', 'manage/uploads/x.png', '\\uploads\\x.png']) {
    assert.equal(resolveImageUrl(stored, BASE), want, stored);
  }
});

test('spaces and special characters are encoded exactly once', () => {
  assert.equal(resolveImageUrl('uploads/a b#c.png', BASE), BASE + 'uploads/a%20b%23c.png');
  assert.equal(resolveImageUrl('uploads/a%20b.png', BASE), BASE + 'uploads/a%20b.png');
});

test('empty, unsafe and unresolvable values give an empty string', () => {
  for (const bad of [null, undefined, '', '   ', 42, 'C:\\Users\\x\\a.png', 'file:///etc/passwd', 'uploads/../../x.png']) {
    assert.equal(resolveImageUrl(bad, BASE), '', String(bad));
  }
  assert.equal(resolveImageUrl('uploads/x.png', ''), ''); // no media base configured: do not guess a host
});

test('local upload previews pass through', () => {
  assert.equal(resolveImageUrl('blob:http://localhost/abc', BASE), 'blob:http://localhost/abc');
  assert.equal(isUsableImageUrl('blob:http://localhost/abc'), true);
  assert.equal(isUsableImageUrl('uploads/x.png'), false);
  assert.equal(isUsableImageUrl(''), false);
});

test('failed images fall back once and are not retried; a new src is tried again', () => {
  assert.deepEqual(imageDisplayState('uploads/x.png', '', BASE), { kind: 'image', url: BASE + 'uploads/x.png' });
  assert.equal(imageDisplayState('uploads/x.png', BASE + 'uploads/x.png', BASE).kind, 'fallback');
  assert.equal(imageDisplayState('uploads/y.png', BASE + 'uploads/x.png', BASE).kind, 'image');
  assert.equal(imageDisplayState('', '', BASE).kind, 'fallback');
  assert.equal(imageDisplayState(null, '', BASE).kind, 'fallback');
});
