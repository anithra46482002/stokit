from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from adminapi import operations
from adminapi.operations import TargetAdminView, is_valid_reward_image, parse_category_id, reward_image_url


def payload(**overrides):
    data = {
        "target_name": "Pens push", "category_id": 5, "target_amount": "20044",
        "reward_description": "Gift hamper", "reward_image": "", "scheme_benefits": "",
        "start_date": "2026-10-09", "end_date": "2026-11-04", "status": "ACTIVE",
    }
    data.update(overrides)
    return data


def category_exists(exists=True):
    manager = mock.Mock()
    manager.filter.return_value.exists.return_value = exists
    return mock.patch.object(operations.Category, "objects", manager), manager


class ParseCategoryIdTests(SimpleTestCase):
    def test_accepts_numeric_ids_as_int_or_string(self):
        self.assertEqual(parse_category_id(5), 5)
        self.assertEqual(parse_category_id("5"), 5)
        self.assertEqual(parse_category_id(" 12 "), 12)

    def test_rejects_names_blanks_booleans_floats_and_non_positive_values(self):
        for bad in ("pens", "", "   ", None, True, False, 5.7, "5.0", "5abc", "-3", 0, "0", -1, [5], {"id": 5}):
            with self.subTest(value=bad):
                self.assertIsNone(parse_category_id(bad))


class TargetCategoryValidationTests(SimpleTestCase):
    def test_numeric_category_id_from_the_dropdown_is_accepted(self):
        patcher, manager = category_exists(True)
        with patcher:
            for submitted in (5, "5"):
                values, error = TargetAdminView._validated(payload(category_id=submitted))
                self.assertIsNone(error)
                self.assertEqual(values["category_id"], 5)
            manager.filter.assert_called_with(pk=5)

    def test_category_name_is_rejected_without_a_database_lookup(self):
        patcher, manager = category_exists(True)
        with patcher:
            values, error = TargetAdminView._validated(payload(category_id="pens"))
        self.assertIsNone(values)
        self.assertEqual(error, {"category_id": "Valid category id required"})
        manager.filter.assert_not_called()

    def test_missing_or_blank_category_id_is_rejected(self):
        patcher, _ = category_exists(True)
        data = payload()
        del data["category_id"]
        with patcher:
            self.assertEqual(TargetAdminView._validated(data)[1], {"category_id": "Valid category id required"})
            self.assertEqual(TargetAdminView._validated(payload(category_id=""))[1], {"category_id": "Valid category id required"})

    def test_boolean_and_fractional_ids_are_not_silently_coerced(self):
        patcher, _ = category_exists(True)
        with patcher:
            for bad in (True, 5.7):
                self.assertEqual(TargetAdminView._validated(payload(category_id=bad))[1], {"category_id": "Valid category id required"})

    def test_unknown_category_is_reported_as_not_found(self):
        patcher, _ = category_exists(False)
        with patcher:
            self.assertEqual(TargetAdminView._validated(payload(category_id=999))[1], {"category_id": "Category not found"})

    def test_partial_update_without_category_keeps_the_existing_category(self):
        patcher, manager = category_exists(True)
        with patcher:
            values, error = TargetAdminView._validated({"target_name": "Renamed"}, partial=True)
        self.assertIsNone(error)
        self.assertNotIn("category_id", values)
        manager.filter.assert_not_called()

    def test_post_with_the_payload_the_form_sends_creates_the_target(self):
        patcher, _ = category_exists(True)
        request = SimpleNamespace(data=payload(category_id="5"), user=SimpleNamespace(id=7))
        created = SimpleNamespace(
            target_id=1, target_name="Pens push", category_id=5, target_amount="20044", reward_description="Gift hamper",
            reward_image=None, scheme_benefits=None, start_date=None, end_date=None, status="ACTIVE")
        with patcher, mock.patch.object(operations.Target.objects, "create", return_value=created) as create:
            response = TargetAdminView().post(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(create.call_args.kwargs["category_id"], 5)
        self.assertEqual(response.data["category_id"], 5)


class RewardImageValidationTests(SimpleTestCase):
    def test_uploaded_paths_and_urls_are_accepted(self):
        for ok in ("uploads/0123456789abcdef0123456789abcdef.png", "uploads/x.webp", "pro-imgs/old_photo.JPG",
                   "https://cdn.example.com/a/b.jpg"):
            with self.subTest(value=ok):
                self.assertTrue(is_valid_reward_image(ok))

    def test_unsafe_or_non_image_values_are_rejected(self):
        for bad in ("../secret.png", "uploads/../x.png", "/etc/passwd.png", "javascript:alert(1)", "data:image/png;base64,AAAA",
                    "uploads/notes.txt", "uploads/run.php", "uploads//x.png", "C:\\x.png", "http://", "https://a b.com/x.png", "efrfrf"):
            with self.subTest(value=bad):
                self.assertFalse(is_valid_reward_image(bad))

    def test_validation_applies_to_the_target_payload(self):
        patcher, _ = category_exists(True)
        with patcher:
            ok, error = TargetAdminView._validated(payload(reward_image="uploads/abc.png"))
            self.assertIsNone(error)
            self.assertEqual(ok["reward_image"], "uploads/abc.png")
            self.assertEqual(TargetAdminView._validated(payload(reward_image="efrfrf"))[1].keys(), {"reward_image"})
            empty, error = TargetAdminView._validated(payload(reward_image=""))
            self.assertIsNone(error)
            self.assertIsNone(empty["reward_image"])

    def test_preview_url_is_built_from_the_media_base(self):
        with self.settings(LEGACY_BASE_URL="https://media.example/"):
            self.assertEqual(reward_image_url("uploads/a.png"), "https://media.example/uploads/a.png")
            self.assertEqual(reward_image_url("https://x.test/a.png"), "https://x.test/a.png")
            self.assertEqual(reward_image_url(None), "")


class TargetPatchCategoryIdTests(SimpleTestCase):
    def test_patch_accepts_and_persists_numeric_category_id(self):
        target = SimpleNamespace(
            target_id=7, target_name="Original", category_id=4, target_amount="20044",
            reward_description="Gift hamper", reward_image=None, scheme_benefits=None,
            start_date=None, end_date=None, status="ACTIVE", updated_at=None,
            save=mock.Mock(),
        )
        target_manager = mock.Mock()
        target_manager.filter.return_value.first.return_value = target
        category_manager = mock.Mock()
        category_manager.filter.return_value.exists.return_value = True
        request = SimpleNamespace(data={"id": 7, "category_id": "5"}, user=SimpleNamespace(id=7))
        with mock.patch.object(operations.Target, "objects", target_manager), \
             mock.patch.object(operations.Category, "objects", category_manager):
            response = TargetAdminView().patch(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(target.category_id, 5)
        self.assertEqual(response.data["category_id"], 5)
        target.save.assert_called_once()
        category_manager.filter.assert_called_with(pk=5)

class TargetAssignmentWorkflowTests(SimpleTestCase):
    def _post(self, data):
        from rest_framework.test import APIRequestFactory, force_authenticate
        request = APIRequestFactory().post('/admin-api/targets/assignments', data, format='json')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role='ADMIN', id=7))
        return operations.TargetAssignmentAdminView.as_view()(request)

    def test_assignment_creates_pending_row_without_creating_achievement(self):
        from decimal import Decimal
        target = SimpleNamespace(target_id=2)
        user = SimpleNamespace(id=9)
        assignment = SimpleNamespace(assignment_id=11, target_id=2, user_id=9,
                                     achieved_amount=Decimal('0.00'), order_count=0,
                                     status='PENDING', achieved_date=None)
        with mock.patch.object(operations.Target, 'objects') as targets, \
             mock.patch.object(operations.LegacyUser, 'objects') as users, \
             mock.patch.object(operations.TargetAssignment, 'objects') as assignments, \
             mock.patch.object(operations.TargetAchievement, 'objects') as achievements, \
             mock.patch('django.db.transaction.atomic'):
            targets.filter.return_value.first.return_value = target
            users.filter.return_value.first.return_value = user
            assignments.filter.return_value.first.return_value = None
            assignments.create.return_value = assignment
            response = self._post({'target_id': 2, 'user_id': 9})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['assignment_id'], 11)
        self.assertEqual(response.data['status'], 'PENDING')
        assignments.create.assert_called_once()
        achievements.create.assert_not_called()

    def test_duplicate_assignment_returns_conflict(self):
        existing = SimpleNamespace(assignment_id=11)
        with mock.patch.object(operations.Target, 'objects') as targets, \
             mock.patch.object(operations.LegacyUser, 'objects') as users, \
             mock.patch.object(operations.TargetAssignment, 'objects') as assignments, \
             mock.patch('django.db.transaction.atomic'):
            targets.filter.return_value.first.return_value = SimpleNamespace(target_id=2)
            users.filter.return_value.first.return_value = SimpleNamespace(id=9)
            assignments.filter.return_value.first.return_value = existing
            response = self._post({'target_id': 2, 'user_id': 9})
        self.assertEqual(response.status_code, 409)
        assignments.create.assert_not_called()

    def test_missing_or_invalid_ids_are_rejected(self):
        for data in ({}, {'target_id': 0, 'user_id': 9}, {'target_id': 2, 'user_id': 'x'}):
            with self.subTest(data=data):
                self.assertEqual(self._post(data).status_code, 400)
