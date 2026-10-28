import axios from 'axios';

const TOKEN_KEY = 'stokit_admin_token';
const USER_KEY = 'stokit_admin_user';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/admin-api/',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// An expired/invalid admin token means the session is over: clear it and return to the login page.
// (Role denials are also HTTP 403 but carry a different message, so they do NOT sign the user out.)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    if ((status === 401 || status === 403) && typeof detail === 'string' && /invalid or expired admin token/i.test(detail)) {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
      if (!window.location.pathname.startsWith('/login')) window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);

// Multipart image upload -> { image_path, url }. image_path is the legacy-relative form ("uploads/xyz.webp").
export async function uploadImage(file) {
  const form = new FormData();
  form.append('file', file);
  // Let Axios/the browser add the multipart boundary; manually setting Content-Type can
  // produce a request without the boundary needed by Django's multipart parser.
  const response = await api.post('uploads', form, { headers: { 'Content-Type': undefined } });
  return response.data;
}

export default api;