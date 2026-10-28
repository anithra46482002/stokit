"""DB-free regression tests for local image serving and image URL resolution.

Root cause these guard against: the /admin/manage/uploads/ route was only registered when
SERVE_LOCAL_UPLOADS was true at import time, so a long-running server started earlier answered 404
for every image while a fresh process / test client answered 200.
"""
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import Client, SimpleTestCase, override_settings
from django.urls import resolve

from .image_urls import image_url

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class ImageServingTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "uploads").mkdir()
        (self.root / "uploads" / "a.png").write_bytes(PNG)
        (self.root / "secret.txt").write_text("secret")
        self.request = SimpleNamespace(build_absolute_uri=lambda p: "http://127.0.0.1:8000" + p)

    def _settings(self, **kw):
        base = dict(DEBUG=False, SERVE_LOCAL_UPLOADS=True, MEDIA_ROOT=self.root,
                    LEGACY_BASE_URL="https://legacy.invalid/admin/manage/")
        base.update(kw)
        return override_settings(**base)

    def _get(self, path):
        return Client(HTTP_HOST="localhost").get(path)

    def test_route_is_always_registered(self):
        with self._settings(SERVE_LOCAL_UPLOADS=False):
            self.assertEqual(resolve("/admin/manage/uploads/a.png").url_name, "local-upload-media")

    def test_serves_exact_bytes_with_debug_false(self):
        with self._settings():
            r = self._get("/admin/manage/uploads/a.png")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r["Content-Type"], "image/png")
            self.assertEqual(b"".join(r.streaming_content), PNG)

    def test_disabled_setting_returns_404_without_restart(self):
        with self._settings(SERVE_LOCAL_UPLOADS=False):
            self.assertEqual(self._get("/admin/manage/uploads/a.png").status_code, 404)

    def test_missing_file_and_traversal_are_404(self):
        with self._settings():
            for p in ("uploads/missing.png", "uploads/../secret.txt", "uploads/..%2fsecret.txt", "uploads/"):
                self.assertEqual(self._get("/admin/manage/" + p).status_code, 404, p)

    def test_absolute_urls_preserved(self):
        with self._settings():
            self.assertEqual(image_url("https://cdn.example/x.png", self.request), "https://cdn.example/x.png")

    def test_local_file_url_has_single_prefix_for_all_stored_shapes(self):
        with self._settings():
            want = "http://127.0.0.1:8000/admin/manage/uploads/a.png"
            for stored in ("uploads/a.png", "/uploads/a.png", "/admin/manage/uploads/a.png",
                           "admin/manage/uploads/a.png", "manage/uploads/a.png"):
                self.assertEqual(image_url(stored, self.request), want, stored)

    def test_legacy_fallback_has_no_duplicated_prefix(self):
        with self._settings():
            self.assertEqual(image_url("uploads/other.png", self.request),
                             "https://legacy.invalid/admin/manage/uploads/other.png")
            self.assertEqual(image_url("/admin/manage/uploads/other.png", self.request),
                             "https://legacy.invalid/admin/manage/uploads/other.png")

    def test_empty_path_returns_none(self):
        with self._settings():
            self.assertIsNone(image_url("", self.request))
