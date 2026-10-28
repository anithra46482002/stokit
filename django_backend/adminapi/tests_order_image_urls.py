"""DB-free regression: order-detail item images use the shared resolver (local uploads, not legacy host)."""
import tempfile
from pathlib import Path

from django.test import RequestFactory, SimpleTestCase, override_settings

from adminapi import order_pages

LEGACY = "https://legacy.invalid/admin/manage/"


class OrderImageUrlTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "uploads").mkdir()
        (self.root / "uploads" / "item.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.request = RequestFactory().get("/admin-api/orders/1", HTTP_HOST="localhost")

    def test_local_upload_resolves_to_this_backend(self):
        with override_settings(MEDIA_ROOT=self.root, LEGACY_BASE_URL=LEGACY, SERVE_LOCAL_UPLOADS=True):
            self.assertEqual(order_pages._image_url("uploads/item.png", self.request),
                             "http://localhost/admin/manage/uploads/item.png")

    def test_missing_local_file_keeps_legacy_url(self):
        with override_settings(MEDIA_ROOT=self.root, LEGACY_BASE_URL=LEGACY, SERVE_LOCAL_UPLOADS=True):
            self.assertEqual(order_pages._image_url("uploads/old.png", self.request), LEGACY + "uploads/old.png")

    def test_empty_path_is_empty_string(self):
        self.assertEqual(order_pages._image_url(None, self.request), "")
        self.assertEqual(order_pages._image_url("  "), "")
