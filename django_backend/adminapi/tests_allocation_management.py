from datetime import date
from decimal import Decimal
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIClient
from .allocation_management import money, reporting_period


class AllocationReportingHelpersTests(SimpleTestCase):
    def test_money_uses_decimal_half_up_rounding(self):
        self.assertEqual(money("12.345"), Decimal("12.35"))
        self.assertEqual(money(None), Decimal("0.00"))

    def test_reporting_period_month_and_as_of_date(self):
        start, end, as_of = reporting_period({"month": "2026-10", "as_of_date": "2026-10-22"})
        self.assertEqual(start, date(2026, 10, 1))
        self.assertEqual(end, date(2026, 11, 1))
        self.assertEqual(as_of, date(2026, 10, 22))

    def test_reporting_period_rejects_invalid_month(self):
        with self.assertRaises(ValueError):
            reporting_period({"month": "October-2026"})

    def test_allocation_routes_resolve(self):
        self.assertEqual(resolve("/admin-api/allocations").url_name, "admin-allocations")
        self.assertEqual(resolve("/admin-api/allocations/42").url_name, "admin-allocation-detail")

    def test_allocation_api_requires_admin_authentication(self):
        response = APIClient().get("/admin-api/allocations")
        self.assertIn(response.status_code, (401, 403))

    def test_serialized_balances_use_month_markers_and_decimal_ledger(self):
        from datetime import datetime
        from types import SimpleNamespace
        from unittest.mock import patch
        from .allocation_management import serialize
        transactions = [
            SimpleNamespace(transaction_type="CREDIT_ADDED", amount=Decimal("500.00"), notes="MONTHLY_RELEASE:2026-09", created_at=datetime(2026, 9, 2)),
            SimpleNamespace(transaction_type="CREDIT_USED", amount=Decimal("200.00"), notes="prior use", created_at=datetime(2026, 9, 5)),
            SimpleNamespace(transaction_type="CREDIT_ADDED", amount=Decimal("100.00"), notes="MONTHLY_RELEASE:2026-10", created_at=datetime(2026, 10, 20)),
            SimpleNamespace(transaction_type="CREDIT_USED", amount=Decimal("50.00"), notes="current use", created_at=datetime(2026, 10, 21)),
        ]
        row = SimpleNamespace(id=4, offer_id=2, user_id=8, payment_amount=Decimal("1000.00"), bonus_percentage=Decimal("10.00"), total_credit=Decimal("2200.00"), used_credit=Decimal("2150.00"), remaining_credit=Decimal("50.00"), duration_months=12, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), payment_date=date(2026, 1, 1), status="ACTIVE", payment_reference=None, notes=None)
        user = SimpleNamespace(username="test-user", fullname="Test User")
        offer = SimpleNamespace(offer_name="Test offer")
        with patch("adminapi.allocation_management.AdvancePayTransaction.objects.filter") as query:
            query.return_value.order_by.return_value = transactions
            result = serialize(row, user, offer, date(2026, 10, 1), date(2026, 11, 1), date(2026, 10, 22))
        # Jan-Sep: 9 x 100 allocated - 200 used before October = 700 carried into October.
        self.assertEqual(result["carry_forward"], "700.00")
        self.assertEqual(result["available_this_month"], "800.00")
        self.assertEqual(result["released_this_month"], "100.00")
        self.assertEqual(result["monthly_credit_release"], "100.00")
        self.assertEqual(result["monthly_bonus"], "100.00")
        self.assertEqual(result["available_now"], "750.00")
        self.assertEqual(result["remaining_this_month"], "750.00")
        self.assertEqual(result["used_this_month"], "50.00")
        self.assertEqual(result["not_yet_released"], "200.00")
        self.assertFalse(result["refund_adjusted_usage_verified"])

    def test_create_endpoint_creates_from_existing_offer_and_user_without_database_writes_in_test(self):
        from datetime import date
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from contextlib import nullcontext
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .allocation_management import AllocationManagementView
        offer = SimpleNamespace(id=3, payment_amount=Decimal("100.00"), bonus_percentage=Decimal("10.00"), duration_months=3, total_credit=Decimal("130.00"))
        user = SimpleNamespace(id=7)
        created = SimpleNamespace(id=99, status="ACTIVE")
        offers = MagicMock(); offers.filter.return_value.first.return_value = offer
        offers.select_for_update.return_value.filter.return_value.first.return_value = offer
        users = MagicMock(); users.filter.return_value.first.return_value = user
        allocations = MagicMock(); allocations.create.return_value = created
        users.select_for_update.return_value.filter.return_value.first.return_value = user
        allocations.select_for_update.return_value.filter.return_value.exists.return_value = False
        request = APIRequestFactory().post("/admin-api/allocations", {"offer_id":3,"user_id":7,"payment_date":"2026-10-20","start_date":"2026-10-20","end_date":"2027-01-20"}, format="json")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role="SUPER_ADMIN"))
        with patch("adminapi.allocation_management.AdvancePayOffer.objects", offers), patch("adminapi.allocation_management.LegacyUser.objects", users), patch("adminapi.allocation_management.AdvancePayAllocation.objects", allocations), patch("adminapi.allocation_management.transaction.atomic", return_value=nullcontext()):
            response = AllocationManagementView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["id"], 99)
        allocations.create.assert_called_once()

    def test_delete_endpoint_cancels_without_deleting_transaction_history(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from contextlib import nullcontext
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .allocation_management import AllocationManagementView
        row = SimpleNamespace(id=9, status="ACTIVE", updated_at=None, save=MagicMock())
        manager = MagicMock(); manager.select_for_update.return_value.filter.return_value.first.return_value = row
        request = APIRequestFactory().delete("/admin-api/allocations/9")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role="SUPER_ADMIN"))
        with patch("adminapi.allocation_management.AdvancePayAllocation.objects", manager), patch("adminapi.allocation_management.transaction.atomic", return_value=nullcontext()):
            response = AllocationManagementView.as_view()(request, allocation_id=9)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.status, "CANCELLED")
        row.save.assert_called_once_with(update_fields=["status", "updated_at"])

    def test_patch_endpoint_updates_metadata_and_status(self):
        from datetime import date
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from contextlib import nullcontext
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .allocation_management import AllocationManagementView
        row = SimpleNamespace(id=12, status="ACTIVE", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), payment_date=date(2026, 1, 1), payment_reference=None, notes=None, updated_at=None, save=MagicMock())
        manager = MagicMock(); manager.select_for_update.return_value.filter.return_value.first.return_value = row
        request = APIRequestFactory().patch("/admin-api/allocations/12", {"status":"COMPLETED", "notes":"Reviewed"}, format="json")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role="SUPER_ADMIN"))
        with patch("adminapi.allocation_management.AdvancePayAllocation.objects", manager), patch("adminapi.allocation_management.transaction.atomic", return_value=nullcontext()):
            response = AllocationManagementView.as_view()(request, allocation_id=12)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.status, "COMPLETED")
        self.assertEqual(row.notes, "Reviewed")
        row.save.assert_called_once()
