# Review-only migration. Do not apply until the user approves a named development database.
from django.db import migrations, models
from django.core.validators import MinValueValidator

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name="CartDiscountSettings", fields=[("id", models.PositiveSmallIntegerField(primary_key=True, default=1, serialize=False, editable=False)), ("enabled", models.BooleanField(default=False)), ("minimum_subtotal", models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])), ("fixed_discount_amount", models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])), ("updated_at", models.DateTimeField(auto_now=True))], options={"db_table": "admin_cart_discount_settings"})]
