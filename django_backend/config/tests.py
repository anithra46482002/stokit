from importlib import reload

from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches, resolve

import config.urls as project_urls

TARGET = "http://127.0.0.1:5173/"


class AdminRedirectTests(SimpleTestCase):
    """/admin used to 404 because Django Admin is deliberately not installed. No database is touched."""
    def setUp(self):
        # Django's default testserver host is not in the production ALLOWED_HOSTS list.
        self.client.defaults["HTTP_HOST"] = "localhost"
    def _reload(self):
        reload(project_urls)
        clear_url_caches()

    def test_admin_paths_redirect_to_react_admin_when_configured(self):
        with override_settings(ADMIN_FRONTEND_URL=TARGET):
            self._reload()
            try:
                for path in ("/admin", "/admin/"):
                    with self.subTest(path=path):
                        response = self.client.get(path)
                        self.assertEqual(response.status_code, 302)
                        self.assertEqual(response["Location"], TARGET)
            finally:
                pass
        self._reload()

    def test_no_redirect_registered_when_not_configured(self):
        with override_settings(ADMIN_FRONTEND_URL=""):
            self._reload()
            self.assertEqual(self.client.get("/admin/").status_code, 404)
        self._reload()

    def test_legacy_and_admin_api_namespaces_are_untouched(self):
        with override_settings(ADMIN_FRONTEND_URL=TARGET):
            self._reload()
            self.assertIsNotNone(resolve("/api/login"))
            self.assertIsNotNone(resolve("/admin-api/auth/login"))
        self._reload()
