"""Database-free tests for the admin image upload (uses a temporary MEDIA_ROOT; no DB access)."""
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.test import Client
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi.uploads import ImageUploadView

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16


def _user(role):
    return SimpleNamespace(is_authenticated=True, role=role, pk=1, principal_type="ADMIN")


class ImageUploadTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = override_settings(DEBUG=False, SERVE_LOCAL_UPLOADS=True, MEDIA_ROOT=Path(self.tmp.name), LEGACY_BASE_URL='https://example.invalid/admin/manage/')
        self.settings.enable()
        self.addCleanup(self.settings.disable)

    def _post(self, role, upload=None):
        data = {"file": upload} if upload is not None else {}
        request = APIRequestFactory().post("/admin-api/uploads", data, format="multipart")
        force_authenticate(request, user=_user(role))
        return ImageUploadView.as_view()(request)

    def test_valid_png_is_stored_under_legacy_relative_path(self):
        response = self._post("ADMIN", SimpleUploadedFile("shot.PNG", PNG, content_type="image/png"))
        self.assertEqual(response.status_code, 201)
        rel = response.data["image_path"]
        self.assertRegex(rel, r"^uploads/[0-9a-f]{32}\.png$")
        self.assertEqual(response.data["url"], "http://testserver/admin/manage/" + rel)
        uploaded_file = Path(self.tmp.name) / rel
        self.assertTrue(uploaded_file.is_file())
        response = Client(HTTP_HOST="testserver").get("/admin/manage/" + rel)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(b"".join(response.streaming_content), PNG)

    def test_webp_signature_is_checked(self):
        ok = self._post("SUPER_ADMIN", SimpleUploadedFile("a.webp", WEBP))
        self.assertEqual(ok.status_code, 201)
        bad = self._post("SUPER_ADMIN", SimpleUploadedFile("a.webp", b"RIFF0000XXXX" + b"\x00" * 8))
        self.assertEqual(bad.status_code, 400)

    def test_rejects_svg_wrong_content_and_missing_file(self):
        self.assertEqual(self._post("ADMIN", SimpleUploadedFile("x.svg", b"<svg onload=alert(1)/>")).status_code, 400)
        self.assertEqual(self._post("ADMIN", SimpleUploadedFile("x.png", b"not really a png")).status_code, 400)
        self.assertEqual(self._post("ADMIN").status_code, 400)

    def test_rejects_oversized_file(self):
        big = SimpleUploadedFile("big.png", PNG + b"\x00" * (5 * 1024 * 1024))
        self.assertEqual(self._post("ADMIN", big).status_code, 400)

    def test_role_without_catalogue_write_access_is_forbidden(self):
        response = self._post("WAREHOUSE_STAFF", SimpleUploadedFile("a.png", PNG))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(list(Path(self.tmp.name).rglob("*.png")), [])
