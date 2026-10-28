from django.core.validators import MinValueValidator
from django.db import models


class CartDiscountSettings(models.Model):
    """Single-row configuration for the fixed cart discount; migration requires approval."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=False)
    minimum_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    fixed_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "admin_cart_discount_settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
