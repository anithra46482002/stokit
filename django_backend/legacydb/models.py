"""Unmanaged mappings of the EXISTING legacy tables, taken from u144866523_stokitDB.sql.

managed=False => Django never creates/alters/drops these tables. Columns/types mirror the
dump. Anything not present in the dump (e.g. zg_checkout.grand_total, which admin PHP
writes) is intentionally NOT modelled until confirmed against the live schema.
"""
from django.db import models


class LegacyUser(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    fullname = models.CharField(max_length=255)
    shop_name = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    category_id = models.CharField(max_length=125, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, default="ACTIVE")  # ACTIVE/INACTIVE/SUSPENDED
    gst = models.CharField(max_length=1, default="N")
    gst_type = models.CharField(max_length=10, null=True, blank=True)
    vip_discount = models.CharField(max_length=1, default="N")
    vip_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    store_maped = models.CharField(max_length=1, default="N")
    profile_picture = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    token = models.CharField(max_length=255, default="")  # legacy single-token column: NOT used for auth any more
    latitude = models.CharField(max_length=125, default="")
    longitude = models.CharField(max_length=125, default="")
    gst_number = models.CharField(max_length=20, null=True, blank=True)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0)
    delivery_charges = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    color_code = models.CharField(max_length=20, null=True, blank=True)
    warehouse_id = models.IntegerField(null=True, blank=True)
    vip_from_date = models.DateField(null=True, blank=True)
    vip_to_date = models.DateField(null=True, blank=True)
    vip_start_date = models.DateField(null=True, blank=True)
    vip_end_date = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "users"


class AdminAccount(models.Model):
    id = models.IntegerField(primary_key=True)  # DEFAULT 0, not auto-increment in the dump
    username = models.CharField(max_length=50)
    email = models.CharField(max_length=100)
    fullname = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=255)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "admins"


class DeliveryBoy(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    email = models.CharField(max_length=100, unique=True)
    fullname = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=255)
    phone = models.CharField(max_length=250)
    address = models.CharField(max_length=250)
    paymentDate = models.CharField(max_length=255, default="")
    token = models.CharField(max_length=1000, default="")
    api_token = models.CharField(max_length=64, null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "delivery_boys"


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=255)
    category_image = models.CharField(max_length=255, null=True, blank=True)
    category_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "zg_category"


class Subcategory(models.Model):
    subcategory_id = models.AutoField(primary_key=True)
    subcategory_name = models.CharField(max_length=255)
    category_id = models.IntegerField()
    subcategory_image = models.CharField(max_length=500, null=True, blank=True)
    subcategory_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "zg_subcategory"


class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=250)
    stock = models.CharField(max_length=250, default="")
    product_name = models.CharField(max_length=255)
    color = models.CharField(max_length=255, default="")
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    product_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product_description = models.TextField(null=True, blank=True)
    product_keywords = models.CharField(max_length=255, default="")
    subtitle = models.CharField(max_length=255, null=True, blank=True)
    brand = models.CharField(max_length=100, null=True, blank=True)
    youtube_link = models.CharField(max_length=255, null=True, blank=True)
    share_image = models.CharField(max_length=255, null=True, blank=True)
    product_details = models.TextField(null=True, blank=True)
    additional_details = models.TextField(null=True, blank=True)
    moq = models.IntegerField(null=True, blank=True, default=0)
    set_of = models.IntegerField(null=True, blank=True, default=1)
    quantity_selected = models.IntegerField(null=True, blank=True, default=0)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0)
    set_contains = models.TextField(null=True, blank=True)  # JSON text; CHECK json_valid in DB
    category_id = models.IntegerField(null=True, blank=True)
    subcategory_id = models.IntegerField(null=True, blank=True)
    top = models.IntegerField(null=True, blank=True, default=0)
    hand = models.IntegerField(null=True, blank=True, default=0)
    top2 = models.IntegerField(default=0)
    hand2 = models.IntegerField(default=0)
    heading5_tag = models.IntegerField(default=0)
    heading6_tag = models.IntegerField(default=0)
    heading7_tag = models.IntegerField(default=0)
    added = models.CharField(max_length=255, default="")
    view = models.CharField(max_length=255, default="1")  # stored as text; API tests compare with the string '1' (no implicit string->number coercion in PostgreSQL)
    highlight = models.BooleanField(default=False)
    gst_applicable = models.CharField(max_length=1, null=True, blank=True, default="N")
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0)
    gst_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    has_disc = models.IntegerField(default=0)
    warehouse_id = models.IntegerField(null=True, blank=True, default=0)
    no_discount_banner = models.CharField(max_length=1, null=True, blank=True, default="N")
    disable_variants = models.CharField(max_length=1, default="N")

    class Meta:
        managed = False
        db_table = "zg_product"


class ProductImage(models.Model):
    image_id = models.AutoField(primary_key=True)
    product_id = models.IntegerField(null=True, blank=True)
    image_path = models.CharField(max_length=255)
    main = models.CharField(max_length=255, default="0")

    class Meta:
        managed = False
        db_table = "zg_product_images"


class Variant(models.Model):
    variant_id = models.AutoField(primary_key=True)
    variant_name = models.CharField(max_length=255)
    variant_price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    product_id = models.IntegerField(null=True, blank=True)
    disc = models.CharField(max_length=255, default="0")
    quantity = models.IntegerField(default=0)
    gst = models.CharField(max_length=1, null=True, blank=True, default="N")
    gst_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    category_id = models.IntegerField(null=True, blank=True)
    subcategory_id = models.IntegerField(null=True, blank=True)
    # Minimum purchase quantity for this variant (a floor, not a required multiple).
    # Real column added by migration 0004; NOT NULL DEFAULT 1 with CHECK (>= 1).
    minimum_buying_count = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = "zg_variant"


class StockLog(models.Model):
    id = models.AutoField(primary_key=True)
    variant_id = models.IntegerField()
    adjustment = models.IntegerField()
    reason = models.TextField(null=True, blank=True)
    admin = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "zg_stock_log"


class Slider(models.Model):
    slider_id = models.AutoField(primary_key=True)
    image_path = models.CharField(max_length=255)
    text_content = models.TextField(default="")
    styled_text = models.CharField(max_length=255, default="")
    styled_color = models.CharField(max_length=50, default="")
    back = models.CharField(max_length=255, default="")
    text_content2 = models.CharField(max_length=255, default="")

    class Meta:
        managed = False
        db_table = "zg_slider"


class Checkout(models.Model):
    order_id = models.AutoField(primary_key=True)
    user = models.CharField(max_length=120, default="")
    full_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_date = models.DateTimeField()
    status = models.CharField(max_length=255)
    delivery_boy_id = models.IntegerField(null=True, blank=True)
    view = models.CharField(max_length=255, default="")
    payment_method = models.CharField(max_length=255, default="")
    shipping_charge = models.CharField(max_length=255, default="0")
    cod_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)

    class Meta:
        managed = False
        db_table = "zg_checkout"


class OrderItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    order_id = models.IntegerField(null=True, blank=True)
    product_id = models.IntegerField(null=True, blank=True)
    variant_id = models.IntegerField(null=True, blank=True)
    product_name = models.CharField(max_length=255)
    variant_name = models.CharField(max_length=255)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = False
        db_table = "zg_order_items"


class OrderStatusHistory(models.Model):
    id = models.AutoField(primary_key=True)
    order_id = models.IntegerField()
    status = models.CharField(max_length=50)
    changed_at = models.DateTimeField()
    message = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "zg_order_status_history"


class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    customer_id = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    sent_by = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    recipient_type = models.CharField(max_length=20, default="all")

    class Meta:
        managed = False
        db_table = "notifications"


class AdvancePayOffer(models.Model):
    id = models.AutoField(primary_key=True)
    offer_name = models.CharField(max_length=255)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    bonus_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    duration_months = models.IntegerField()
    total_credit = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=8, default="ACTIVE")
    image_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "advance_pay_offers"


class AdvancePayAllocation(models.Model):
    id = models.AutoField(primary_key=True)
    offer_id = models.IntegerField()
    user_id = models.IntegerField()
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    bonus_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    duration_months = models.IntegerField()
    total_credit = models.DecimalField(max_digits=10, decimal_places=2)
    used_credit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    remaining_credit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, default="ACTIVE")
    payment_date = models.DateField()
    payment_reference = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "advance_pay_allocations"


class Warehouse(models.Model):
    warehouse_id = models.AutoField(primary_key=True)
    warehouse_name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    place = models.CharField(max_length=50, null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "zg_warehouse"

class Target(models.Model):
    target_id = models.AutoField(primary_key=True)
    target_name = models.CharField(max_length=255)
    category_id = models.IntegerField()
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reward_description = models.TextField()
    reward_image = models.CharField(max_length=255, null=True, blank=True)
    scheme_benefits = models.TextField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, default="ACTIVE")
    created_by = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "zg_targets"


class TargetAssignment(models.Model):
    assignment_id = models.AutoField(primary_key=True)
    target_id = models.IntegerField()
    user_id = models.IntegerField()
    achieved_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_count = models.IntegerField(default=0)
    status = models.CharField(max_length=10, default="PENDING")
    achieved_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "zg_target_assignments"


class TargetAchievement(models.Model):
    achievement_id = models.AutoField(primary_key=True)
    target_id = models.IntegerField()
    user_id = models.IntegerField()
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_count = models.IntegerField(default=0)
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_achieved = models.BooleanField(default=False)
    achieved_date = models.DateField(null=True, blank=True)
    last_order_date = models.DateField(null=True, blank=True)
    last_order_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "zg_target_achievements"

class Salesman(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50)
    email = models.CharField(max_length=100)
    fullname = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address = models.TextField(null=True, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hire_date = models.DateField(null=True, blank=True)
    target_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    token = models.CharField(max_length=64, null=True, blank=True)
    api_token = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "salesmen"

class AdvancePayTransaction(models.Model):
    id = models.AutoField(primary_key=True)
    allocation_id = models.IntegerField()
    user_id = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20)
    reference_id = models.IntegerField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'advance_pay_transactions'
