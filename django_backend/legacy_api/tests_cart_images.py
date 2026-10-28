"""DB-free regression tests: GET /api/cart_api_test must return the product image for every cart line.

Root cause guarded against: the cart SQL selected the product's main image (main_image) but the item dict never
exposed it, so no cart line carried an image_url and the cart showed no pictures.
"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from legacy_api.tests_cart import PRODUCTS, FakeCartDb, add, cart_env, fetch_cart

LEGACY = "https://legacy.invalid/admin/manage/"
DEFAULT = "https://projects.teleber.com/stokit/pro-imgs/default.jpg"


def lines(cart):
    out = {}
    for bucket in ("discount_available", "discount_not_available"):
        for group in cart["cart_items"][bucket].values():
            for item in group["items"]:
                out[(item["product_name"], item["variant_id"])] = item
    return out


@override_settings(LEGACY_BASE_URL=LEGACY, SERVE_LOCAL_UPLOADS=False)
class CartImageTests(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch.dict(PRODUCTS, {k: dict(v) for k, v in PRODUCTS.items()})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_relative_path_resolves_against_the_backend_media_base(self):
        PRODUCTS[11]["image"] = "uploads/pen.png"
        with cart_env(FakeCartDb()):
            add(11, (0, 1))
            item = next(iter(lines(fetch_cart()).values()))
        self.assertEqual(item["image_url"], LEGACY + "uploads/pen.png")

    def test_absolute_url_is_kept_unchanged_and_prefixes_are_not_duplicated(self):
        PRODUCTS[11]["image"] = "https://cdn.example/a/b.png?v=2"
        PRODUCTS[12]["image"] = "admin/manage/uploads/x.png"
        with cart_env(FakeCartDb()):
            add(11, (0, 1))
            add(12, (0, 1))
            found = {i["product_name"]: i["image_url"] for i in lines(fetch_cart()).values()}
        self.assertEqual(found[PRODUCTS[11]["name"]], "https://cdn.example/a/b.png?v=2")
        self.assertEqual(found[PRODUCTS[12]["name"]], LEGACY + "uploads/x.png")

    def test_missing_image_gets_the_fallback_and_the_cart_still_works(self):
        PRODUCTS[11]["image"] = None
        with cart_env(FakeCartDb()):
            add(11, (0, 2))
            item = next(iter(lines(fetch_cart()).values()))
        self.assertEqual(item["image_url"], DEFAULT)
        self.assertEqual(item["quantity"], 2)

    def test_variants_use_their_own_products_image_and_images_never_mix(self):
        PRODUCTS[13]["image"] = "uploads/p13.png"
        PRODUCTS[11]["image"] = "uploads/p11.png"
        with cart_env(FakeCartDb()):
            add(13, (101, 1), (102, 2))
            add(11, (0, 1))
            found = lines(fetch_cart())
        by_product = {}
        for (name, variant_id), item in found.items():
            by_product.setdefault(name, set()).add(item["image_url"])
        self.assertEqual(by_product[PRODUCTS[13]["name"]], {LEGACY + "uploads/p13.png"})
        self.assertEqual(by_product[PRODUCTS[11]["name"]], {LEGACY + "uploads/p11.png"})

    def test_refresh_and_quantity_change_keep_the_image(self):
        PRODUCTS[11]["image"] = "uploads/pen.png"
        with cart_env(FakeCartDb()):
            add(11, (0, 1))
            first = next(iter(lines(fetch_cart()).values()))
            add(11, (0, 3))
            second = next(iter(lines(fetch_cart()).values()))
        self.assertEqual(first["image_url"], second["image_url"])
        self.assertEqual(second["quantity"], 4)


from legacy_api.cart_discount_testing import module_fixtures
setUpModule, tearDownModule = module_fixtures()  # no saved cart-discount row: promotion unconfigured, no DB access
