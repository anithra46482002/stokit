const TOKEN_KEY = 'stokit_admin_token';
const USER_KEY = 'stokit_admin_user';

const VALID_ROLES = new Set([
  'SUPER_ADMIN',
  'ADMIN',
  'SALESMAN',
  'WAREHOUSE_STAFF',
  'DELIVERY_BOY',
]);

export function validateLoginResponse(data) {
  if (!data || typeof data.token !== 'string' || !data.token.trim()) {
    throw new Error(data?.message || 'The login response did not include a valid token.');
  }
  if (!data.user || typeof data.user !== 'object' || Array.isArray(data.user)) {
    throw new Error('The login response did not include user information.');
  }
  if (typeof data.user.role !== 'string' || !VALID_ROLES.has(data.user.role)) {
    throw new Error('This account has no active admin role assigned. Contact a Super Admin.');
  }
  return { token: data.token, user: data.user };
}

export function clearAdminSession(storage = globalThis.sessionStorage) {
  try {
    storage?.removeItem(TOKEN_KEY);
    storage?.removeItem(USER_KEY);
  } catch {
    // Storage may be blocked by browser privacy settings; callers still fail closed.
  }
}

export function persistAdminSession(data, storage = globalThis.sessionStorage) {
  const session = validateLoginResponse(data);
  try {
    if (!storage) throw new Error('Session storage is unavailable.');
    storage.setItem(TOKEN_KEY, session.token);
    storage.setItem(USER_KEY, JSON.stringify(session.user));
    if (storage.getItem(TOKEN_KEY) !== session.token ||
        storage.getItem(USER_KEY) !== JSON.stringify(session.user)) {
      throw new Error('Session storage verification failed.');
    }
  } catch {
    clearAdminSession(storage);
    throw new Error('Could not save the login session in this browser. Enable session storage and try again.');
  }
  return session;
}

// Pure routing decision, evaluated on EVERY render (never cache it inside a route element).
// Returns the path to redirect to, or null when the visitor may stay on `pathname`.
export function guardRedirect(pathname, session) {
  const onLogin = pathname === '/login' || pathname.startsWith('/login/');
  if (!session && !onLogin) return '/login';
  if (session && onLogin) return '/';
  return null;
}
export function getAdminSession(storage = globalThis.sessionStorage) {
  try {
    const token = storage?.getItem(TOKEN_KEY);
    const rawUser = storage?.getItem(USER_KEY);
    if (!token || !rawUser) {
      clearAdminSession(storage);
      return null;
    }
    const user = JSON.parse(rawUser);
    return validateLoginResponse({ token, user });
  } catch {
    clearAdminSession(storage);
    return null;
  }
}