"""Test helpers for the persisted Cart Discount Settings (no database is touched).

The customer cart and checkout read adminapi.CartDiscountSettings on every request. Unit tests replace that
storage with a mock manager, so they never read or write real settings, customers or orders.
"""
from types import SimpleNamespace
from unittest import mock

from adminapi import cart_discount


def settings_row(enabled=True, minimum_subtotal="8000.00", fixed_discount_amount="800.00"):
    """A stand-in for the saved settings row (what the admin Cart Discount page stores)."""
    return SimpleNamespace(enabled=enabled, minimum_subtotal=minimum_subtotal, fixed_discount_amount=fixed_discount_amount)


def patch_cart_discount_settings(row=None, error=None):
    """Patch the settings storage: `row` is the saved row (None = no row saved); `error` is a DB error to raise."""
    manager = mock.Mock()
    if error is not None:
        manager.filter.side_effect = error
    else:
        manager.filter.return_value.first.return_value = row
    return mock.patch.object(cart_discount.CartDiscountSettings, "objects", manager)


def module_fixtures():
    """(setUpModule, tearDownModule) for test modules that exercise cart/checkout but not the promotion.

    They run with no saved settings row, i.e. the promotion is NOT configured and nothing is discounted - which is
    also what proves that no hardcoded fallback exists.
    """
    patchers = []

    def set_up():
        patcher = patch_cart_discount_settings(row=None)
        patcher.start()
        patchers.append(patcher)

    def tear_down():
        while patchers:
            patchers.pop().stop()

    return set_up, tear_down
