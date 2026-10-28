from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.conf import settings


class SessionQuerySet(models.QuerySet):
    def active(self, now=None):
        """Sessions that may authenticate: not revoked, not past expires_at, not inactive too long."""
        now = now or timezone.now()
        q = Q(revoked_at__isnull=True) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        days = settings.SESSION_INACTIVITY_DAYS
        if days and days > 0:
            q &= Q(last_activity_at__gt=now - timedelta(days=days))
        return self.filter(q)


class UserDeviceSession(models.Model):
    """One row per active login of a Flutter customer account (max MAX_ACTIVE_SESSIONS).

    The raw bearer token is never stored: only its SHA-256 hex digest. The legacy
    `users.token` column is no longer consulted for authentication.
    NOTE: "device" is a label only. The current Flutter client sends no verified device id,
    so the server limits concurrent *sessions*, not physical devices.
    """

    user = models.ForeignKey(
        "legacydb.LegacyUser",
        on_delete=models.CASCADE,
        related_name="device_sessions",
        db_constraint=False,  # never add an FK constraint to the legacy `users` table
    )
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_activity_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=32, blank=True, default="")
    user_agent = models.CharField(max_length=255, blank=True, default="")  # informational only
    ip_address = models.GenericIPAddressField(null=True, blank=True)       # informational only

    objects = SessionQuerySet.as_manager()

    class Meta:
        db_table = "accounts_userdevicesession"
        indexes = [models.Index(fields=["user", "revoked_at"], name="uds_user_revoked_idx")]

    def __str__(self):
        return f"session {self.pk} user={self.user_id}"


class DeviceToken(models.Model):
    """Push (FCM) device tokens sent to /api/notify. Replaces the PHP tokens.txt file."""

    user = models.ForeignKey("legacydb.LegacyUser", on_delete=models.CASCADE, db_constraint=False)
    device_token = models.TextField()
    device_token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "accounts_devicetoken"
        constraints = [models.UniqueConstraint(fields=["user", "device_token_hash"], name="uniq_user_devicetoken")]


class PasswordResetOTP(models.Model):
    """Secure replacement for the PHP reset flow (which used a fixed OTP)."""

    user = models.ForeignKey("legacydb.LegacyUser", on_delete=models.CASCADE, db_constraint=False)
    otp_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_passwordresetotp"

class CheckoutPayload(models.Model):
    """Persist the legacy saveCheck JSON payload without writing arbitrary files to disk."""
    user_id = models.IntegerField(db_index=True)
    payload = models.JSONField()
    legacy_order_id = models.PositiveBigIntegerField(unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "accounts_checkoutpayload"
        ordering = ["-created_at"]
class AdminRoleAssignment(models.Model):
    PRINCIPAL_TYPES = [
        ('ADMIN', 'Legacy admin account'),
        ('SALESMAN', 'Legacy salesman account'),
        ('DELIVERY_BOY', 'Legacy delivery account'),
    ]
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin'),
        ('ADMIN', 'Admin'),
        ('SALESMAN', 'Salesman'),
        ('WAREHOUSE_STAFF', 'Warehouse Staff'),
        ('DELIVERY_BOY', 'Delivery Boy'),
    ]
    principal_type = models.CharField(max_length=20, choices=PRINCIPAL_TYPES)
    principal_id = models.IntegerField(db_index=True)
    role = models.CharField(max_length=24, choices=ROLE_CHOICES)
    active = models.BooleanField(default=True)
    assigned_by_admin_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'accounts_adminroleassignment'
        constraints = [models.UniqueConstraint(fields=['principal_type', 'principal_id'], name='uniq_admin_role_principal')]
