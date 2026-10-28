"""Behavioural regression tests for ProductCRUDView._clean_product_extras (discount banners + set_contains).

Before the fix, `json` was not imported in adminapi/crud.py, so any request touching set_contains/discount_banners
raised NameError (HTTP 500) and product Save Changes appeared to do nothing.
"""
from django.test import SimpleTestCase

from adminapi.crud import ProductCRUDView

clean = ProductCRUDView._clean_product_extras


class CleanProductExtrasTests(SimpleTestCase):
    def test_json_string_set_contains_is_decoded(self):
        raw, banners = clean({"set_contains": '[{"name": "k", "qty": 2}]'})
        self.assertEqual(raw, [{"name": "k", "qty": 2}])
        self.assertIsNone(banners)

    def test_invalid_json_is_a_validation_error_not_a_crash(self):
        with self.assertRaisesMessage(ValueError, "set_contains must be valid JSON"):
            clean({"set_contains": "{not json"})

    def test_scalar_set_contains_rejected(self):
        with self.assertRaises(ValueError):
            clean({"set_contains": 5})

    def test_banners_are_trimmed_and_order_is_kept(self):
        _, banners = clean({"set_contains": [], "discount_banners": [" uploads/a.png ", "uploads/b.png"]})
        self.assertEqual(banners, ["uploads/a.png", "uploads/b.png"])

    def test_empty_list_means_clear_all_banners(self):
        _, banners = clean({"set_contains": [], "discount_banners": []})
        self.assertEqual(banners, [])

    def test_blank_or_non_string_banner_paths_rejected(self):
        for bad in ([""], ["  "], [None], [5], "uploads/a.png"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                clean({"set_contains": [], "discount_banners": bad})

    def test_more_than_ten_banners_rejected(self):
        with self.assertRaisesMessage(ValueError, "at most 10"):
            clean({"set_contains": [], "discount_banners": [f"uploads/{i}.png" for i in range(11)]})
