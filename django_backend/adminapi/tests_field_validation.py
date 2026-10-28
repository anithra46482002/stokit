from django.test import SimpleTestCase
from adminapi.field_validation import clean_email, clean_indian_mobile, normalize_indian_mobile

class SharedFieldValidationTests(SimpleTestCase):
    def test_email_addresses(self):
        self.assertEqual(clean_email('  user@gmail.com  '), ('user@gmail.com', ''))
        self.assertEqual(clean_email('person@company.co.in'), ('person@company.co.in', ''))
        for value in ('bad@@gmail.com', 'user@domain', 'a..b@gmail.com'):
            self.assertTrue(clean_email(value)[1], value)
        self.assertEqual(clean_email('', required=False), ('', ''))
        self.assertTrue(clean_email('')[1])

    def test_indian_mobile_formats(self):
        self.assertEqual(normalize_indian_mobile('9876543210'), '9876543210')
        self.assertEqual(normalize_indian_mobile('+91 98765-43210'), '9876543210')
        self.assertEqual(normalize_indian_mobile('09876543210'), '9876543210')
        for value in ('1234567890', '987654321', '98765432100', '98765abc10', '+1 202 555 0100'):
            self.assertIsNone(normalize_indian_mobile(value), value)
        self.assertEqual(clean_indian_mobile('', required=False), ('', ''))
        self.assertTrue(clean_indian_mobile('', required=True)[1])