from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi.operations import AdvancePaymentAdminView, _validated_advance_duration
from adminapi.offers import AdvancePaymentOffersView, _offer_out


def admin_user():
    return SimpleNamespace(is_authenticated=True, role="ADMIN", pk=1, principal_type="ADMIN")


class AdvanceOfferDurationValidationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def post(self, months):
        request = self.factory.post("/admin-api/advance-payments", {
            "offer_name": "Test Offer", "payment_amount": "30000", "bonus_percentage": "10",
            "duration_months": months, "status": "ACTIVE",
        }, format="json")
        force_authenticate(request, user=admin_user())
        return AdvancePaymentOffersView.as_view()(request)

    def patch(self, months):
        row = SimpleNamespace(
            id=7, offer_name="Test Offer", payment_amount=Decimal("30000"),
            bonus_percentage=Decimal("10"), duration_months=12,
            total_credit=Decimal("36000"), status="ACTIVE", image_path="",
            updated_at=None, save=MagicMock(),
        )
        request = self.factory.patch("/admin-api/advance-payments?id=7", {
            "id": 7, "duration_months": months,
        }, format="json")
        force_authenticate(request, user=admin_user())
        with patch("adminapi.operations.AdvancePayOffer.objects.filter") as query:
            query.return_value.first.return_value = row
            response = AdvancePaymentOffersView.as_view()(request)
        return response, row

    def test_duration_parser_accepts_12_and_above_integer_months(self):
        for months in (12, 13, 18, 24):
            with self.subTest(months=months):
                self.assertEqual(_validated_advance_duration(months), months)

    def test_duration_parser_rejects_missing_invalid_fractional_and_under_12(self):
        for months in (None, "", "abc", 0, -1, 11, 11.5, 12.5, "NaN"):
            with self.subTest(months=months):
                self.assertIsNone(_validated_advance_duration(months))

    def test_post_rejects_11_months_without_writing(self):
        with patch("adminapi.offers.AdvancePayOffer.objects.create") as create:
            response = self.post(11)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Duration must be at least 12 months.", str(response.data))
        create.assert_not_called()

    def test_post_accepts_12_13_18_and_24_months_and_recalculates_benefit(self):
        for months in (12, 13, 18, 24):
            with self.subTest(months=months):
                offer = SimpleNamespace(
                    id=9, offer_name="Test Offer", payment_amount=Decimal("30000"),
                    bonus_percentage=Decimal("10"), duration_months=months,
                    total_credit=Decimal("3000") * months, status="ACTIVE", image_path="",
                )
                with patch("adminapi.offers.AdvancePayOffer.objects.create", return_value=offer):
                    response = self.post(months)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(Decimal(response.data["benefit"]), Decimal("3000") * months)
                self.assertEqual(response.data["duration_months"], months)

    def test_patch_rejects_11_months_without_saving(self):
        response, row = self.patch(11)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Duration must be at least 12 months.", str(response.data))
        row.save.assert_not_called()

    def test_patch_accepts_durations_above_12_and_recalculates(self):
        for months in (12, 13, 18, 24):
            with self.subTest(months=months):
                response, row = self.patch(months)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(row.duration_months, months)
                self.assertEqual(row.total_credit, Decimal("3000") * months)
                row.save.assert_called_once()

    def test_legacy_operations_post_rejects_11_months(self):
        request = self.factory.post("/admin-api/advance-payments", {
            "offer_name": "Test Offer", "payment_amount": "30000", "bonus_percentage": "10", "duration_months": 11,
        }, format="json")
        force_authenticate(request, user=admin_user())
        with patch("adminapi.operations.AdvancePayOffer.objects.create") as create:
            response = AdvancePaymentAdminView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    def test_offer_list_contract_keeps_existing_fields_and_dynamic_benefit(self):
        offer = SimpleNamespace(
            id=5, offer_name="Offer", payment_amount=Decimal("30000"), bonus_percentage=Decimal("10"),
            duration_months=18, image_path="uploads/test.webp", status="ACTIVE",
        )
        with patch("adminapi.offers.settings.MEDIA_ROOT") as media_root, patch("adminapi.offers.settings.LEGACY_BASE_URL", "https://example.test/admin/manage/"):
            media_root.__truediv__.return_value.is_file.return_value = False
            result = _offer_out(offer)
        for field in ("id", "offer_name", "payment_amount", "bonus_percentage", "duration_months", "benefit", "status", "image_path", "image_url"):
            self.assertIn(field, result)
        self.assertEqual(result["duration_months"], 18)
        self.assertEqual(Decimal(result["benefit"]), Decimal("54000.00"))