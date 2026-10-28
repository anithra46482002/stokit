"""DB-free regression tests for the shared image URL helper and the endpoints that use it.

Root causes these guard against (found in the image URL audit):
  * several Flutter endpoints still built `LEGACY_BASE_URL + value` by hand, so an absolute value (the default
    avatar, a CDN URL, the placeholder) became `https://host/admin/manage/https://...`, empty values became a
    bare directory URL, and a stored `admin/manage/` prefix was duplicated;
  * `/api/category` returned raw relative sub-category paths and `manage//` double slashes;
  * the admin offers API built URLs by hand (no escaping, DEBUG-only local branch that the serving route 404s).
"""
import json
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from adminapi.image_urls import image_url, legacy_url, normalize_relative
from adminapi import offers
from adminapi.offers import _offer_out
from legacy_api import common, views_auth, views_catalog, views_finance
from legacy_api.common import legacy_image_url

LEGACY = "https://legacy.invalid/admin/manage/"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16


class HelperTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "uploads").mkdir()
        (self.root / "uploads" / "my photo (1).png").write_bytes(PNG)
        self.request = SimpleNamespace(build_absolute_uri=lambda p: "http://localhost" + p)
        ctx = override_settings(MEDIA_ROOT=self.root, LEGACY_BASE_URL=LEGACY, SERVE_LOCAL_UPLOADS=True)
        ctx.enable()
        self.addCleanup(ctx.disable)

    def test_relative_path(self):
        self.assertEqual(image_url("uploads/x.png", self.request), LEGACY + "uploads/x.png")

    def test_absolute_https_url_untouched(self):
        self.assertEqual(image_url("https://cdn.example/a/b.png?v=2", self.request), "https://cdn.example/a/b.png?v=2")

    def test_absolute_url_with_space_is_escaped_once(self):
        self.assertEqual(image_url("https://cdn.example/a b.png"), "https://cdn.example/a%20b.png")
        self.assertEqual(image_url("https://cdn.example/a%20b.png"), "https://cdn.example/a%20b.png")

    def test_protocol_relative_url_gets_https(self):
        self.assertEqual(image_url("//cdn.example/x.png"), "https://cdn.example/x.png")

    def test_repeated_prefixes_never_duplicate(self):
        for stored in ("admin/manage/admin/manage/uploads/x.png", "/manage/admin/manage/uploads/x.png",
                       "\\admin\\manage\\uploads\\x.png"):
            self.assertEqual(image_url(stored), LEGACY + "uploads/x.png", stored)

    def test_null_and_empty_return_none(self):
        for empty in (None, "", "   "):
            self.assertIsNone(image_url(empty))
            self.assertIsNone(legacy_url(empty))

    def test_spaces_and_special_characters_are_encoded_once(self):
        self.assertEqual(image_url("uploads/a b#c?d.png"), LEGACY + "uploads/a%20b%23c%3Fd.png")
        self.assertEqual(image_url("uploads/a%20b.png"), LEGACY + "uploads/a%20b.png")  # not %2520

    def test_local_file_with_spaces_and_parentheses_is_served_locally(self):
        self.assertEqual(image_url("uploads/my photo (1).png", self.request),
                         "http://localhost/admin/manage/uploads/my%20photo%20%281%29.png")

    def test_windows_paths_and_traversal_are_never_published(self):
        for bad in ("C:\\Users\\.MSI\\x.png", "c:/x.png", "file:///etc/passwd", "uploads/../../secret.png",
                    "..\\secret.png"):
            self.assertIsNone(image_url(bad, self.request), bad)
            self.assertIsNone(normalize_relative(bad), bad)

    def test_unset_legacy_base_returns_none_instead_of_fabricating(self):
        with override_settings(LEGACY_BASE_URL=""):
            self.assertIsNone(image_url("uploads/x.png"))

    def test_legacy_image_url_fallbacks(self):
        self.assertEqual(legacy_image_url("", None, ""), "")
        self.assertIsNone(legacy_image_url(None, None, None))
        self.assertEqual(legacy_image_url("../x.png", None, "FALLBACK"), "FALLBACK")
        self.assertEqual(legacy_image_url("https://www.w3schools.com/howto/img_avatar.png", None, "x"),
                         "https://www.w3schools.com/howto/img_avatar.png")
        self.assertEqual(legacy_image_url("uploads/x.png", None, ""), LEGACY + "uploads/x.png")


class EndpointTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "uploads").mkdir()
        (self.root / "uploads" / "cat.png").write_bytes(PNG)
        self.rf = RequestFactory()
        ctx = override_settings(MEDIA_ROOT=self.root, LEGACY_BASE_URL=LEGACY, SERVE_LOCAL_UPLOADS=True)
        ctx.enable()
        self.addCleanup(ctx.disable)
        for patcher in (
            mock.patch.object(common.services, "parse_bearer", return_value="t"),
            mock.patch.object(common.services, "authenticate_token",
                              return_value=(object(), {"username": "u", "email": "e"})),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_category_endpoint_images(self):
        cats = [{"category_id": 1, "category_name": "A", "category_image": "uploads/cat.png"},
                {"category_id": 2, "category_name": "B", "category_image": None}]
        subs = [{"subcategory_id": 9, "subcategory_name": "S", "subcategory_image": "uploads/s.png"},
                {"subcategory_id": 10, "subcategory_name": "T", "subcategory_image": None}]

        def fake_fetchall(sql, params=()):
            return cats if "FROM zg_category" in sql else subs

        request = self.rf.get("/api/category", HTTP_HOST="localhost")
        with mock.patch.object(views_catalog, "fetchone", return_value={"category_id": 1, "category_name": "A"}), \
                mock.patch.object(views_catalog, "fetchall", side_effect=fake_fetchall):
            body = json.loads(views_catalog.category(request).content)
        items = body if isinstance(body, list) else body["categories"]
        self.assertEqual(items[0]["image_url"], "http://localhost/admin/manage/uploads/cat.png")
        self.assertEqual(items[1]["image_url"], "")  # no bare directory URL for a missing image
        self.assertEqual(items[0]["subcategories"][0]["image_url"], LEGACY + "uploads/s.png")
        self.assertIsNone(items[0]["subcategories"][1]["image_url"])

    def test_profile_default_and_stored_pictures(self):
        row = {"profile_picture": "", "created_at": None, "shop_name": "s", "fullname": "o", "address": "a",
               "city": "c", "username": "u", "phone": "p", "email": "e", "status": "ACTIVE",
               "vip_discount": 0, "vip_percentage": 0, "store_maped": "N"}
        request = self.rf.get("/api/profile", HTTP_HOST="localhost")
        for stored, want in (("", "https://www.w3schools.com/howto/img_avatar.png"),
                             ("https://cdn.example/me.png", "https://cdn.example/me.png"),
                             ("uploads/me.png", LEGACY + "uploads/me.png")):
            with mock.patch.object(views_auth, "fetchone", return_value=dict(row, profile_picture=stored)):
                body = json.loads(views_auth.profile(request).content)
            self.assertEqual(body["profile"]["profile_picture_url"], want, stored)

    def test_advance_pay_flutter_img_url(self):
        now = "2026-10-26T00:00:00"
        base = {"id": 1, "assigned": "N", "offer_name": "o", "payment_amount": Decimal("1000"),
                "bonus_percentage": Decimal("5"), "duration_months": 3, "total_credit": Decimal("150"),
                "status": "ACTIVE", "created_at": now, "updated_at": now}
        rows = [dict(base, image_path="uploads/o.png"), dict(base, id=2, image_path=None),
                dict(base, id=3, image_path="https://cdn.example/o.png")]
        request = self.rf.post("/api/advance_pay", data=json.dumps({}), content_type="application/json",
                               HTTP_HOST="localhost")
        with mock.patch.object(views_finance, "fetchall", return_value=rows), \
                mock.patch.object(views_finance, "fetchone", return_value={"total": 3}):
            body = json.loads(views_finance.advance_pay(request).content)
        urls = [o["imgUrl"] for o in body["data"]["offers"]]
        self.assertEqual(urls, [LEGACY + "uploads/o.png", "", "https://cdn.example/o.png"])

    def test_admin_offer_out_uses_shared_helper(self):
        offer = SimpleNamespace(id=1, offer_name="o", payment_amount=Decimal("1000"), bonus_percentage=Decimal("5"),
                                duration_months=3, status="ACTIVE", image_path="uploads/a b.png")
        out = _offer_out(offer)
        self.assertEqual(out["image_url"], LEGACY + "uploads/a%20b.png")
        self.assertEqual(out["image_path"], "uploads/a b.png")  # stored value is never rewritten
        offer.image_path = ""
        self.assertEqual(_offer_out(offer)["image_url"], "")
        offer.image_path = "https://cdn.example/o.png"
        self.assertEqual(_offer_out(offer)["image_url"], "https://cdn.example/o.png")


class SharedOfferImageTests(SimpleTestCase):
    """Replacing/deleting an offer must not delete an image file another offer still references."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "uploads" / "offers").mkdir(parents=True)
        self.file = self.root / "uploads" / "offers" / "shared.webp"
        self.file.write_bytes(PNG)
        ctx = override_settings(MEDIA_ROOT=self.root)
        ctx.enable()
        self.addCleanup(ctx.disable)

    def _remove(self, still_referenced):
        qs = mock.Mock()
        qs.exists.return_value = still_referenced
        with mock.patch.object(offers.AdvancePayOffer.objects, "filter", return_value=qs):
            offers.remove_offer_image("uploads/offers/shared.webp")

    def test_shared_file_is_kept(self):
        self._remove(True)
        self.assertTrue(self.file.exists())

    def test_unreferenced_file_is_removed(self):
        self._remove(False)
        self.assertFalse(self.file.exists())

    def test_paths_outside_offers_folder_are_never_removed(self):
        outside = self.root / "uploads" / "keep.png"
        outside.write_bytes(PNG)
        with mock.patch.object(offers.AdvancePayOffer.objects, "filter", return_value=mock.Mock(exists=lambda: False)):
            offers.remove_offer_image("uploads/keep.png")
        self.assertTrue(outside.exists())
