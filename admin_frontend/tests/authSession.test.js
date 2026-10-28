import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getAdminSession,
  guardRedirect,
  persistAdminSession,
  validateLoginResponse,
} from '../src/authSession.js';

function makeStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

const validResponse = {
  token: 'test-only-token',
  user: {
    id: 17,
    username: 'test-super-admin',
    role: 'SUPER_ADMIN',
    principal_type: 'ADMIN',
    permissions_configured: true,
  },
};

test('successful SUPER_ADMIN response persists and restores a valid session for the root route', () => {
  const storage = makeStorage();
  const saved = persistAdminSession(validResponse, storage);
  assert.equal(saved.token, validResponse.token);
  assert.equal(saved.user.role, 'SUPER_ADMIN');
  assert.equal(storage.getItem('stokit_admin_token'), validResponse.token);
  assert.deepEqual(JSON.parse(storage.getItem('stokit_admin_user')), validResponse.user);
  assert.deepEqual(getAdminSession(storage), validResponse);
});

test('missing-token response is rejected and never becomes a stored session', () => {
  const storage = makeStorage();
  assert.throws(() => persistAdminSession({ user: validResponse.user }, storage), /valid token/i);
  assert.equal(getAdminSession(storage), null);
});

test('missing user object is rejected', () => {
  assert.throws(() => validateLoginResponse({ token: 'test-only-token' }), /user information/i);
});

test('unassigned or unsupported role is rejected and cannot enter the root route', () => {
  const storage = makeStorage();
  assert.throws(
    () => persistAdminSession({ token: 'test-only-token', user: { id: 17, role: null } }, storage),
    /no active admin role/i,
  );
  assert.equal(getAdminSession(storage), null);
});

test('malformed stored user JSON fails closed and clears the session', () => {
  const storage = makeStorage();
  storage.setItem('stokit_admin_token', 'test-only-token');
  storage.setItem('stokit_admin_user', 'undefined');
  assert.equal(getAdminSession(storage), null);
  assert.equal(storage.getItem('stokit_admin_token'), null);
  assert.equal(storage.getItem('stokit_admin_user'), null);
});
test('guardRedirect re-evaluates against the CURRENT session (regression: login bounced back to /login)', () => {
  const storage = makeStorage();
  // Visitor starts unauthenticated on a protected route.
  assert.equal(guardRedirect('/', getAdminSession(storage)), '/login');
  // Same route, evaluated again after sign-in: must now be allowed.
  persistAdminSession(validResponse, storage);
  assert.equal(guardRedirect('/', getAdminSession(storage)), null);
  assert.equal(guardRedirect('/orders', getAdminSession(storage)), null);
  // A signed-in user opening /login is sent to the dashboard.
  assert.equal(guardRedirect('/login', getAdminSession(storage)), '/');
});

test('guardRedirect keeps unauthenticated and tampered-storage visitors on the login page', () => {
  assert.equal(guardRedirect('/login', null), null);
  assert.equal(guardRedirect('/products', null), '/login');
  const storage = makeStorage();
  storage.setItem('stokit_admin_token', 'forged');
  storage.setItem('stokit_admin_user', JSON.stringify({ username: 'x', role: 'NOT_A_ROLE' }));
  assert.equal(getAdminSession(storage), null);
  assert.equal(guardRedirect('/', getAdminSession(storage)), '/login');
});