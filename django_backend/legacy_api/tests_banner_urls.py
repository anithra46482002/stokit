"""DB-free regression tests for the public /api/banner image_url contract.

Root cause these guard against: /api/banner always built LEGACY_BASE_URL + image_path, so images
uploaded through the new admin (stored under MEDIA_ROOT/uploads) pointed at the legacy PHP host,
where they 404, and replaced banners never appeared in the app.
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from legacy_api import views_catalog

LEGACY = "https://legacy.invalid/admin/manage/"


class BannerUrlTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "uploads").mkdir()
        (self.root / "uploads" / "local.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 16)
        self.rf = RequestFactory()

    def _urls(self, paths, **overrides):
        settings_kw = dict(MEDIA_ROOT=self.root, LEGACY_BASE_URL=LEGACY, SERVE_LOCAL_UPLOADS=True)
        settings_kw.update(overrides)
        rows = [{"id": i + 1, "image_path": p} for i, p in enumerate(paths)]
        request = self.rf.get("/api/banner", HTTP_HOST="localhost")
        with override_settings(**settings_kw), \
                mock.patch.object(views_catalog, "fetchone", return_value={"total": len(rows)}), \
                mock.patch.object(views_catalog, "fetchall", return_value=rows):
            body = json.loads(views_catalog.banner(request).content)
        return [b["image_url"] for b in body["banner"]]

    def test_local_upload_is_served_by_this_backend(self):
        self.assertEqual(self._urls(["uploads/local.png"]), ["http://localhost/admin/manage/uploads/local.png"])

    def test_legacy_style_prefixed_path_resolves_to_local_file(self):
        self.assertEqual(self._urls(["/admin/manage/uploads/local.png"]),
                         ["http://localhost/admin/manage/uploads/local.png"])

    def test_file_not_stored_locally_keeps_legacy_url(self):
        self.assertEqual(self._urls(["uploads/only-on-legacy.png"]), [LEGACY + "uploads/only-on-legacy.png"])

    def test_serving_disabled_falls_back_to_legacy_url(self):
        self.assertEqual(self._urls(["uploads/local.png"], SERVE_LOCAL_UPLOADS=False), [LEGACY + "uploads/local.png"])

    def test_absolute_url_is_preserved_not_double_prefixed(self):
        self.assertEqual(self._urls(["https://cdn.example/x.png"]), ["https://cdn.example/x.png"])

    def test_empty_path_returns_empty_string_not_directory_url(self):
        self.assertEqual(self._urls([None, "  "]), ["", ""])
