from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import AdminRoleAssignment
from legacydb.models import AdminAccount, Salesman, DeliveryBoy

class Command(BaseCommand):
    help = 'Provision a trusted role mapping for an existing legacy admin, salesman or delivery account.'

    def add_arguments(self, parser):
        parser.add_argument('--principal-type', choices=['ADMIN','SALESMAN','DELIVERY_BOY'], default='ADMIN')
        parser.add_argument('--principal-id', '--admin-id', dest='principal_id', type=int, required=True)
        parser.add_argument('--role', choices=[x[0] for x in AdminRoleAssignment.ROLE_CHOICES], required=True)
        parser.add_argument('--assigned-by', type=int, help='Legacy admins.id for the active Super Admin authorizing this change.')
        parser.add_argument('--bootstrap-super-admin', action='store_true', help='One-time operator bootstrap for the first Super Admin mapping.')

    @transaction.atomic
    def handle(self, *args, **options):
        principal_type = options['principal_type']
        principal_id = options['principal_id']
        role = options['role']
        actor_id = options.get('assigned_by')
        if role == 'SUPER_ADMIN' and principal_type != 'ADMIN':
            raise CommandError('SUPER_ADMIN must be mapped to a legacy admins-table account.')
        if principal_type == 'SALESMAN' and role != 'SALESMAN':
            raise CommandError('A salesman-table principal may only receive the SALESMAN role.')
        if principal_type == 'DELIVERY_BOY' and role != 'DELIVERY_BOY':
            raise CommandError('A delivery_boys-table principal may only receive the DELIVERY_BOY role.')
        models = {'ADMIN': AdminAccount, 'SALESMAN': Salesman, 'DELIVERY_BOY': DeliveryBoy}
        if not models[principal_type].objects.filter(pk=principal_id).exists():
            raise CommandError(f'Target {principal_type} principal id does not exist in its legacy table.')
        has_super = AdminRoleAssignment.objects.filter(role='SUPER_ADMIN', active=True).exists()
        if not has_super:
            if not (options['bootstrap_super_admin'] and principal_type == 'ADMIN' and role == 'SUPER_ADMIN' and actor_id is None):
                raise CommandError('No active Super Admin exists. Use --bootstrap-super-admin once for a verified legacy admins row after reviewed migration.')
        else:
            if actor_id is None:
                raise CommandError('--assigned-by is required after bootstrap.')
            actor = AdminRoleAssignment.objects.filter(principal_type='ADMIN', principal_id=actor_id, role='SUPER_ADMIN', active=True).first()
            if not actor:
                raise CommandError('--assigned-by must identify an active Super Admin in the admins table.')
        assignment, created = AdminRoleAssignment.objects.update_or_create(
            principal_type=principal_type,
            principal_id=principal_id,
            defaults={'role': role, 'active': True, 'assigned_by_admin_id': actor_id},
        )
        verb = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{verb} role assignment: {principal_type} id {principal_id} -> {role}'))

