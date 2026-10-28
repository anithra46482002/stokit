"""Opt-in admin CRUD integration tests for an isolated MariaDB schema containing legacy tables.
Set STOKIT_RUN_MARIADB_INTEGRATION=1 and run `manage.py test adminapi.mariadb_integration`.
"""
import os
from django.core import signing
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from accounts.models import AdminRoleAssignment
from legacydb.models import AdminAccount, Category

RUN = os.environ.get('STOKIT_RUN_MARIADB_INTEGRATION') == '1'

class MariaDBAdminCrudTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        if not RUN:
            self.skipTest('Set STOKIT_RUN_MARIADB_INTEGRATION=1 after provisioning a disposable MariaDB schema.')
        self.client = APIClient()
        next_id = (AdminAccount.objects.order_by('-id').values_list('id', flat=True).first() or 1000) + 1
        self.admin = AdminAccount.objects.create(id=next_id, username=f'crud-admin-{next_id}',
            email=f'crud-admin-{next_id}@example.invalid', fullname='CRUD Test Admin', password='unused')
        AdminRoleAssignment.objects.create(principal_type='ADMIN', principal_id=self.admin.pk, role='SUPER_ADMIN', active=True)
        self.token = signing.dumps({'admin_id': self.admin.pk}, salt='stokit.admin-token')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+self.token)
        self.created_category_id = None

    def tearDown(self):
        if RUN:
            if self.created_category_id:
                Category.objects.filter(pk=self.created_category_id).delete()
            AdminRoleAssignment.objects.filter(principal_type='ADMIN', principal_id=self.admin.pk).delete()
            AdminAccount.objects.filter(pk=self.admin.pk).delete()
            if hasattr(self, 'admin2'):
                AdminRoleAssignment.objects.filter(principal_type='ADMIN', principal_id=self.admin2.pk).delete()
                AdminAccount.objects.filter(pk=self.admin2.pk).delete()

    def test_category_crud_validation_pagination_and_authorization(self):
        invalid = self.client.post('/admin-api/categories', {'name':' '}, format='json')
        self.assertEqual(invalid.status_code, 400)
        created = self.client.post('/admin-api/categories', {'name':f'CRUD test {self.admin.pk}'}, format='json')
        self.assertEqual(created.status_code, 201)
        self.created_category_id = created.json()['id']
        listing = self.client.get('/admin-api/categories', {'page':1,'page_size':1})
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['page_size'], 1)
        self.assertLessEqual(len(listing.json()['results']), 1)
        updated = self.client.patch('/admin-api/categories', {'id':self.created_category_id,'name':f'Updated {self.admin.pk}'}, format='json')
        self.assertEqual(updated.status_code, 200)
        deleted = self.client.delete('/admin-api/categories', {'id':self.created_category_id}, format='json')
        self.assertEqual(deleted.status_code, 204)
        self.created_category_id = None

    def test_salesman_role_cannot_create_categories(self):
        self.admin2 = AdminAccount.objects.create(id=self.admin.pk+1, username=f'salesman-role-{self.admin.pk}',
            email=f'salesman-role-{self.admin.pk}@example.invalid', fullname='Sales Role Test', password='unused')
        AdminRoleAssignment.objects.create(principal_type='ADMIN', principal_id=self.admin2.pk, role='SALESMAN', active=True)
        token = signing.dumps({'admin_id':self.admin2.pk}, salt='stokit.admin-token')
        client = APIClient(); client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
        response = client.post('/admin-api/categories', {'name':'Should be denied'}, format='json')
        self.assertEqual(response.status_code, 403)
        AdminRoleAssignment.objects.filter(principal_type='ADMIN', principal_id=self.admin2.pk).delete()
        AdminAccount.objects.filter(pk=self.admin2.pk).delete()
