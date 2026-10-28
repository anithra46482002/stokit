import json

from django.conf import settings
from .permissions import AdminRolePermission
from accounts.hashers import hash_password
from django.db import IntegrityError, connection, transaction
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from django.utils import timezone
from legacydb.models import Category, Subcategory, Product, LegacyUser, Checkout, OrderItem, OrderStatusHistory, StockLog, Variant, Warehouse, AdvancePayAllocation, AdvancePayOffer
from .field_validation import clean_email, clean_indian_mobile, clean_text
from .db_errors import log_db_error

from .image_urls import image_url as _image_url


class CategoryCRUDView(APIView):
    required_resource = "catalogue"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = Category.objects.order_by('category_name')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(category_name__icontains=search)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid pagination'}, status=400)
        rows = list(qs[(page-1)*size:page*size])
        base = getattr(settings, 'LEGACY_BASE_URL', '')
        return Response({'count': qs.count(), 'page': page, 'page_size': size, 'results': [
            {'id': x.category_id, 'name': x.category_name, 'image': x.category_image,
             'image_url': _image_url(x.category_image, request),
             'active': x.category_active}
            for x in rows
        ]})

    def post(self, request):
        name = clean_text(request.data.get('name', ''))
        if not name or len(name) > 255:
            return Response({'name': 'Name is required and must be <=255 characters'}, status=400)
        row = Category.objects.create(category_name=name, category_image=request.data.get('image') or None,
                                      category_active=bool(request.data.get('active', True)))
        return Response({'id': row.category_id, 'name': row.category_name, 'image': row.category_image,
                         'active': row.category_active}, status=201)

    def patch(self, request):
        try:
            cid = int(request.data.get('id'))
        except (ValueError, TypeError):
            return Response({'id': 'Valid category id required'}, status=400)
        row = Category.objects.filter(pk=cid).first()
        if not row:
            return Response({'detail': 'Category not found'}, status=404)
        if 'name' in request.data:
            name = clean_text(request.data['name'])
            if not name or len(name) > 255:
                return Response({'name': 'Name is required and must be <=255 characters'}, status=400)
            row.category_name = name
        if 'image' in request.data:
            row.category_image = request.data['image'] or None
        if 'active' in request.data:
            row.category_active = bool(request.data['active'])
        row.save(update_fields=['category_name', 'category_image', 'category_active'])
        return Response({'id': row.category_id, 'name': row.category_name, 'image': row.category_image,
                         'active': row.category_active})

    def delete(self, request):
        try:
            cid = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError):
            return Response({'id': 'Valid category id required'}, status=400)
        row = Category.objects.filter(pk=cid).first()
        if not row:
            return Response({'detail': 'Category not found'}, status=404)
        if Subcategory.objects.filter(category_id=cid).exists() or Product.objects.filter(category_id=cid).exists():
            return Response({
                'detail': 'This category is still used by subcategories or products. Deactivate it instead, or move those records first.',
                'code': 'category_in_use',
            }, status=409)
        try:
            # Keep deletion atomic. Legacy tables may have additional database constraints
            # that are not represented by Django ForeignKey fields in unmanaged models.
            with transaction.atomic():
                row.delete()
        except IntegrityError:
            return Response({
                'detail': 'The database rejected this deletion because another record still references this category. Move or remove the related record first, then retry.',
                'code': 'category_referenced',
            }, status=409)
        except Exception as exc:
            log_db_error('Category delete', exc)
            return Response({'detail': 'Category could not be deleted due to a database error. Check the Django server log for the underlying error.'}, status=500)
        return Response(status=204)

class SubcategoryCRUDView(APIView):
    required_resource = "catalogue"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = Subcategory.objects.order_by('subcategory_name')
        if request.query_params.get('category_id'):
            qs = qs.filter(category_id=request.query_params['category_id'])
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(subcategory_name__icontains=search)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid pagination'}, status=400)
        rows = list(qs[(page-1)*size:page*size])
        names = dict(Category.objects.filter(pk__in={x.category_id for x in rows}).values_list('category_id', 'category_name'))
        return Response({'count': qs.count(), 'page': page, 'page_size': size, 'results': [
            {'id': x.subcategory_id, 'name': x.subcategory_name, 'category_id': x.category_id,
             'category_name': names.get(x.category_id, ''),
             'image': x.subcategory_image, 'image_url': _image_url(x.subcategory_image, request),
             'active': x.subcategory_active}
            for x in rows
        ]})

    def post(self, request):
        name = clean_text(request.data.get('name', ''))
        try:
            cid = int(request.data.get('category_id'))
        except (ValueError, TypeError):
            return Response({'category_id': 'Valid category id required'}, status=400)
        if not name:
            return Response({'name': 'Name is required'}, status=400)
        if not Category.objects.filter(pk=cid).exists():
            return Response({'category_id': 'Category not found'}, status=400)
        row = Subcategory.objects.create(subcategory_name=name, category_id=cid,
            subcategory_image=request.data.get('image') or None,
            subcategory_active=bool(request.data.get('active', True)))
        return Response({'id': row.subcategory_id, 'name': row.subcategory_name,
            'category_id': row.category_id, 'image': row.subcategory_image, 'active': row.subcategory_active}, status=201)

    def patch(self, request):
        try:
            sid = int(request.data.get('id'))
        except (ValueError, TypeError):
            return Response({'id': 'Valid subcategory id required'}, status=400)
        row = Subcategory.objects.filter(pk=sid).first()
        if not row:
            return Response({'detail': 'Subcategory not found'}, status=404)
        if 'name' in request.data:
            name = clean_text(request.data['name'])
            if not name:
                return Response({'name': 'Name cannot be empty'}, status=400)
            row.subcategory_name = name
        if 'category_id' in request.data:
            try:
                cid = int(request.data['category_id'])
            except (ValueError, TypeError):
                return Response({'category_id': 'Valid category id required'}, status=400)
            if not Category.objects.filter(pk=cid).exists():
                return Response({'category_id': 'Category not found'}, status=400)
            row.category_id = cid
        if 'image' in request.data:
            row.subcategory_image = request.data['image'] or None
        if 'active' in request.data:
            row.subcategory_active = bool(request.data['active'])
        row.save(update_fields=['subcategory_name', 'category_id', 'subcategory_image', 'subcategory_active'])
        return Response({'id': row.subcategory_id, 'name': row.subcategory_name,
            'category_id': row.category_id, 'image': row.subcategory_image, 'active': row.subcategory_active})

    def delete(self, request):
        try:
            sid = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError):
            return Response({'id': 'Valid subcategory id required'}, status=400)
        row = Subcategory.objects.filter(pk=sid).first()
        if not row:
            return Response({'detail': 'Subcategory not found'}, status=404)
        if Product.objects.filter(subcategory_id=sid).exists():
            return Response({'detail': 'Subcategory is in use; deactivate instead'}, status=409)
        row.delete()
        return Response(status=204)

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.db import transaction
from legacydb.models import Product, ProductImage, Variant

# Minimum Purchase Quantity: the smallest quantity a customer may buy (a floor, not a required multiple).
# Public field `minimum_buying_count`; products store it in zg_product.moq, variants in
# zg_variant.minimum_buying_count. Accepts positive whole numbers only.
MIN_PURCHASE_QUANTITY_MAX = 2147483647
MIN_PURCHASE_QUANTITY_MESSAGE = 'Minimum purchase quantity must be a positive whole number.'


def _validated_minimum_purchase_quantity(value):
    if isinstance(value, bool) or value is None:
        raise ValueError(MIN_PURCHASE_QUANTITY_MESSAGE)
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip()
        if not (text.isascii() and text.isdigit()):
            raise ValueError(MIN_PURCHASE_QUANTITY_MESSAGE)
        number = int(text)
    else:
        # floats / Decimals (even 2.0) are rejected: only whole-number input is accepted
        raise ValueError(MIN_PURCHASE_QUANTITY_MESSAGE)
    if number < 1:
        raise ValueError(MIN_PURCHASE_QUANTITY_MESSAGE)
    if number > MIN_PURCHASE_QUANTITY_MAX:
        raise ValueError('Minimum purchase quantity is too large.')
    return number


class ProductCRUDView(APIView):
    @staticmethod
    def _get_discount_banners(product_id):
        with connection.cursor() as cursor:
            cursor.execute('SELECT image_path FROM zg_discount_banners WHERE product_id = %s ORDER BY id ASC', [product_id])
            return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def _parse_set_contains(value):
        if not value:
            return []
        try:
            decoded = json.loads(value) if isinstance(value, str) else value
            return decoded if isinstance(decoded, (list, dict)) else []
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _clean_product_extras(data):
        raw = data.get('set_contains', [])
        if isinstance(raw, str):
            try: raw = json.loads(raw)
            except (TypeError, ValueError): raise ValueError('set_contains must be valid JSON')
        if not isinstance(raw, (list, dict)):
            raise ValueError('set_contains must be a JSON array or object')
        banners = data.get('discount_banners')
        if banners is not None:
            if not isinstance(banners, list) or any(not isinstance(v, str) or not v.strip() for v in banners):
                raise ValueError('discount_banners must be an array of non-empty image paths')
            banners = [v.strip() for v in banners]
            if len(banners) > 10: raise ValueError('A product can have at most 10 discount banners')
        return raw, banners

    @staticmethod
    def _validated_no_discount_banner(value):
        normalized = str(value).strip().upper()
        if normalized not in ('Y', 'N'):
            raise ValueError('no_discount_banner must be Y or N')
        return normalized

    @staticmethod
    def _validated_disable_variants(value):
        normalized = str(value).strip().upper()
        if normalized not in ('Y', 'N'):
            raise ValueError('disable_variants must be Y or N')
        return normalized

    # The product's Minimum Purchase Quantity is stored in the existing legacy column zg_product.moq
    # (the Flutter product detail already reads it as purchase_details.moq, floored at 1),
    # so no product schema change is needed. The admin API exposes it as `minimum_buying_count`
    # (preferred) and, for backward compatibility, as the alias `minimum_buying_quantity`.
    @staticmethod
    def _validated_minimum_buying_quantity(value):
        return _validated_minimum_purchase_quantity(value)

    @staticmethod
    def _resolve_minimum_purchase_quantity(data):
        """Reads the preferred field and the legacy alias from a request body.

        Returns (provided, value, errors). `errors` is a dict ready for an HTTP 400 response.
        Precedence: either name is accepted on its own; if both are sent they must carry the same
        value, otherwise the request is rejected (nothing is silently ignored or overridden).
        """
        names = [name for name in ('minimum_buying_count', 'minimum_buying_quantity') if name in data]
        if not names:
            return False, None, None
        values = {}
        for name in names:
            try:
                values[name] = _validated_minimum_purchase_quantity(data[name])
            except ValueError as exc:
                return True, None, {name: str(exc)}
        if len(set(values.values())) > 1:
            message = ('minimum_buying_count and minimum_buying_quantity are the same setting; '
                       'send one of them or send matching values.')
            return True, None, {'minimum_buying_count': message, 'minimum_buying_quantity': message}
        return True, next(iter(values.values())), None

    @staticmethod
    def _minimum_buying_quantity_out(row):
        # Legacy rows default moq to 0 (or NULL); the customer app already treats that as 1.
        try:
            return max(1, int(getattr(row, 'moq', None) or 0))
        except (ValueError, TypeError):
            return 1

    @classmethod
    def _minimum_purchase_fields_out(cls, row):
        value = cls._minimum_buying_quantity_out(row)
        # Both names are returned during the compatibility period.
        return {'minimum_buying_count': value, 'minimum_buying_quantity': value}
    required_resource = "catalogue"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = Product.objects.order_by('-product_id')
        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(product_name__icontains=search) | Q(code__icontains=search))
        if request.query_params.get('category_id'):
            qs = qs.filter(category_id=request.query_params['category_id'])
        if request.query_params.get('id'):
            try:
                qs = qs.filter(product_id=int(request.query_params['id']))
            except (ValueError, TypeError):
                return Response({'detail': 'Invalid product id'}, status=400)
        if request.query_params.get('visible') in ('0', '1'):
            qs = qs.filter(view=request.query_params['visible'])
        if request.query_params.get('warehouse_id'):
            qs = qs.filter(warehouse_id=request.query_params['warehouse_id'])
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid pagination'}, status=400)
        total = qs.count()
        products = list(qs[(page-1)*size:page*size])
        ids = [p.product_id for p in products]
        discount_banners = {pid: [] for pid in ids}
        if ids and all(isinstance(product, Product) for product in products):
            with connection.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(ids))
                cursor.execute(f'SELECT product_id, image_path FROM zg_discount_banners WHERE product_id IN ({placeholders}) ORDER BY id ASC', ids)
                for banner_pid, image_path in cursor.fetchall():
                    discount_banners.setdefault(banner_pid, []).append(image_path)
        images = {}
        for x in ProductImage.objects.filter(product_id__in=ids).order_by('product_id', '-main', 'image_id'):
            images.setdefault(x.product_id, []).append({'id': x.image_id, 'image_path': x.image_path, 'main': x.main})
        cat_names = dict(Category.objects.filter(pk__in={p.category_id for p in products}).values_list('category_id', 'category_name'))
        variants = {}
        for x in Variant.objects.filter(product_id__in=ids).order_by('variant_id'):
            variants.setdefault(x.product_id, []).append({'id': x.variant_id, 'name': x.variant_name,
                'price': str(x.variant_price), 'mrp': str(x.mrp), 'quantity': x.quantity, 'discount': x.disc,
                'gst': x.gst, 'gst_price': str(x.gst_price if x.gst_price is not None else 0),
                'minimum_buying_count': x.minimum_buying_count})
        return Response({'count': total, 'page': page, 'page_size': size, 'results': [
            {'id': p.product_id, 'name': p.product_name, 'code': p.code, 'price': str(p.product_price),
             'mrp': str(p.mrp or 0), 'discount': str(p.product_discount or 0), 'category_id': p.category_id,
             'subcategory_id': p.subcategory_id, 'visible': p.view, 'highlight': p.highlight,
             'stock': p.stock, 'color': p.color, 'gst_applicable': p.gst_applicable or 'N',
             'gst_percentage': str(p.gst_percentage or 0), 'gst_price': str(p.gst_price or 0),
             'no_discount_banner': p.no_discount_banner if p.no_discount_banner in ('Y', 'N') else 'N',
             'disable_variants': p.disable_variants if p.disable_variants in ('Y', 'N') else 'N',
             **self._minimum_purchase_fields_out(p),
             'description': p.product_description or '', 'keywords': p.product_keywords or '',
             'subtitle': getattr(p, 'subtitle', '') or '', 'brand': getattr(p, 'brand', '') or '',
             'product_details': p.product_details or '', 'additional_details': p.additional_details or '',
             'category_name': cat_names.get(p.category_id, ''), 'warehouse_id': p.warehouse_id,
             'image_url': _image_url((images.get(p.product_id) or [{}])[0].get('image_path'), request),
             'images': [{**img, 'url': _image_url(img['image_path'], request)} for img in images.get(p.product_id, [])],
             'variants': variants.get(p.product_id, []), 'discount_banners': discount_banners.get(p.product_id, []), 'set_contains': self._parse_set_contains(getattr(p, 'set_contains', None))} for p in products]})

    def post(self, request):
        data = request.data
        name = clean_text(data.get('name', ''))
        code = str(data.get('code', '')).strip()
        try:
            price = Decimal(str(data.get('price')))
            cid = int(data.get('category_id'))
            mrp = Decimal(str(data.get('mrp', data.get('price'))))
        except (ValueError, TypeError, InvalidOperation):
            return Response({'detail': 'Valid price, MRP and category_id are required'}, status=400)
        if not name or not price.is_finite() or not mrp.is_finite() or price < 0 or mrp < 0:
            return Response({'detail': 'Product name is required and prices must be finite and non-negative'}, status=400)
        if not Category.objects.filter(pk=cid).exists():
            return Response({'category_id': 'Category not found'}, status=400)
        subid = data.get("subcategory_id") or None
        if subid:
            try: subid = int(subid)
            except (ValueError, TypeError): return Response({"subcategory_id": "Valid subcategory id required"}, status=400)
            if not Subcategory.objects.filter(pk=subid, category_id=cid).exists():
                return Response({"subcategory_id": "Subcategory does not belong to this category"}, status=400)
        minimum_buying_quantity = 1  # documented default when neither field is sent (the app already floors moq at 1)
        provided, resolved_quantity, quantity_errors = self._resolve_minimum_purchase_quantity(data)
        if quantity_errors:
            return Response(quantity_errors, status=400)
        if provided:
            minimum_buying_quantity = resolved_quantity
        try:
            set_contains, discount_banners = self._clean_product_extras(data)
            no_discount_banner = self._validated_no_discount_banner(data.get('no_discount_banner', 'N'))
            disable_variants = self._validated_disable_variants(data.get('disable_variants', 'N'))
            gst_applicable = str(data.get('gst_applicable', 'N')).strip().upper()
            if gst_applicable not in ('Y', 'N'):
                return Response({'gst_applicable': 'Choose Yes or No'}, status=400)
            gst_pct = Decimal(str(data.get('gst_percentage', 0) or 0))
            gst_price = Decimal(str(data.get('gst_price', 0) or 0))
            discount = Decimal(str(data.get('discount', 0) or 0))
            if not all(value.is_finite() for value in (gst_pct, gst_price, discount)) or min(gst_pct, gst_price, discount) < 0 or gst_pct > 100:
                return Response({'detail': 'GST percentage, GST price and discount must be finite and non-negative; GST percentage cannot exceed 100'}, status=400)
            row = Product.objects.create(product_name=name, code=code, stock=str(data.get('stock', '')), color=str(data.get('color', '')),
                product_price=price, mrp=mrp, product_discount=discount, gst_applicable=gst_applicable,
                gst_percentage=gst_pct, gst_price=gst_price,
                no_discount_banner=no_discount_banner, disable_variants=disable_variants, moq=minimum_buying_quantity,
                product_description=str(data.get('description', '')),
                product_keywords=str(data.get('keywords', ''))[:255],
                subtitle=str(data.get('subtitle', '') or '')[:255],
                brand=str(data.get('brand', '') or '')[:100],
                # Flutter product detail endpoints read these legacy columns, not the admin-only aliases.
                product_details=str(data.get('product_details', data.get('description', ''))),
                additional_details=str(data.get('additional_details', data.get('keywords', ''))),
                set_contains=json.dumps(set_contains, ensure_ascii=False),
                category_id=cid, subcategory_id=subid,
                view=str(data.get('visible', '1')), highlight=bool(data.get('highlight', False)))
        except Exception as exc:
            log_db_error('Product create', exc)
            return Response({'detail': 'Product could not be created against the current legacy schema'}, status=400)
        if discount_banners is not None:
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        for image_path in discount_banners:
                            cursor.execute('INSERT INTO zg_discount_banners (product_id, image_path) VALUES (%s, %s)', [row.product_id, image_path])
            except Exception as exc:
                log_db_error('Product discount banner create', exc)
                row.delete()
                return Response({'detail': 'Product discount banners could not be saved against the current legacy schema'}, status=400)
        return Response({'id': row.product_id, 'name': row.product_name, 'code': row.code,
            'price': str(row.product_price), 'category_id': row.category_id, 'subcategory_id': row.subcategory_id,
            'subtitle': getattr(row, 'subtitle', '') or '', 'brand': getattr(row, 'brand', '') or '',
            'discount_banners': discount_banners or [], 'set_contains': set_contains,
            'no_discount_banner': row.no_discount_banner if row.no_discount_banner in ('Y', 'N') else 'N',
            'disable_variants': row.disable_variants if row.disable_variants in ('Y', 'N') else 'N',
            **self._minimum_purchase_fields_out(row)}, status=201)

    def patch(self, request):
        try:
            pid = int(request.data.get('id'))
        except (ValueError, TypeError):
            return Response({'id': 'Valid product id required'}, status=400)
        row = Product.objects.filter(pk=pid).first()
        if not row:
            return Response({'detail': 'Product not found'}, status=404)
        data = request.data
        try:
            if 'set_contains' in data or 'discount_banners' in data:
                set_contains, discount_banners = self._clean_product_extras({'set_contains': data.get('set_contains', row.set_contains or '[]'), 'discount_banners': data.get('discount_banners') if 'discount_banners' in data else None})
            else:
                set_contains, discount_banners = None, None
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        if 'name' in data:
            if not clean_text(data['name']): return Response({'name': 'Name cannot be empty'}, status=400)
            row.product_name = clean_text(data['name'])
        if 'code' in data:
            if not str(data['code']).strip(): return Response({'code': 'Code cannot be empty'}, status=400)
            row.code = str(data['code']).strip()
        if 'subtitle' in data:
            row.subtitle = str(data.get('subtitle') or '')[:255]
        if 'brand' in data:
            row.brand = str(data.get('brand') or '')[:100]
        if 'set_contains' in data:
            row.set_contains = json.dumps(set_contains, ensure_ascii=False)
        for target_field, key in (('product_price', 'price'), ('mrp', 'mrp'), ('product_discount', 'discount')):
            if key in data:
                try: value = Decimal(str(data[key]))
                except (ValueError, TypeError, InvalidOperation): return Response({key: 'Enter a valid amount'}, status=400)
                if not value.is_finite() or value < 0: return Response({key: 'Amount must be finite and non-negative'}, status=400)
                setattr(row, target_field, value)
        if "category_id" in data:
            try: cid = int(data["category_id"])
            except (ValueError, TypeError): return Response({"category_id": "Valid category id required"}, status=400)
            if not Category.objects.filter(pk=cid).exists(): return Response({"category_id": "Category not found"}, status=400)
            row.category_id = cid
        if "subcategory_id" in data:
            subid = data["subcategory_id"] or None
            if subid:
                try: subid = int(subid)
                except (ValueError, TypeError): return Response({"subcategory_id": "Valid subcategory id required"}, status=400)
                if not Subcategory.objects.filter(pk=subid, category_id=row.category_id).exists():
                    return Response({"subcategory_id": "Subcategory does not belong to this category"}, status=400)
            row.subcategory_id = subid
        elif row.subcategory_id and "category_id" in data and not Subcategory.objects.filter(pk=row.subcategory_id, category_id=row.category_id).exists():
            return Response({"subcategory_id": "Existing subcategory does not belong to the selected category; choose a matching subcategory first"}, status=400)
        if "no_discount_banner" in data:
            try:
                row.no_discount_banner = self._validated_no_discount_banner(data["no_discount_banner"])
            except ValueError as exc:
                return Response({"no_discount_banner": str(exc)}, status=400)
        if "disable_variants" in data:
            try:
                row.disable_variants = self._validated_disable_variants(data["disable_variants"])
            except ValueError as exc:
                return Response({"disable_variants": str(exc)}, status=400)
        # Omitted in both spellings -> the stored moq is preserved. Conflicting spellings -> HTTP 400.
        quantity_provided, resolved_quantity, quantity_errors = self._resolve_minimum_purchase_quantity(data)
        if quantity_errors:
            return Response(quantity_errors, status=400)
        if quantity_provided:
            row.moq = resolved_quantity
        if "visible" in data: row.view = str(data["visible"])
        if "highlight" in data: row.highlight = bool(data["highlight"])
        for target_field, key in (('stock', 'stock'), ('color', 'color'), ('gst_applicable', 'gst_applicable'),
                                  ('gst_percentage', 'gst_percentage'), ('gst_price', 'gst_price'),
                                  ('product_description', 'description'), ('product_keywords', 'keywords'),
                                  ('product_details', 'product_details'), ('additional_details', 'additional_details')):
            if key in data:
                value = data[key]
                if target_field in ('gst_percentage', 'gst_price'):
                    try: value = Decimal(str(value or 0))
                    except (ValueError, TypeError, InvalidOperation): return Response({key: 'Enter a valid numeric value'}, status=400)
                    if not value.is_finite() or value < 0 or (target_field == 'gst_percentage' and value > 100): return Response({key: 'Value is outside the allowed range'}, status=400)
                if target_field == 'gst_applicable':
                    value = str(value).strip().upper()
                    if value not in ('Y', 'N'): return Response({key: 'Choose Yes or No'}, status=400)
                if target_field == 'product_keywords': value = str(value)[:255]
                setattr(row, target_field, value)
        # Keep Flutter's legacy product detail fields aligned with the admin fields it edits.
        if 'description' in data and 'product_details' not in data:
            row.product_details = str(data.get('description') or '')
        if 'keywords' in data and 'additional_details' not in data:
            row.additional_details = str(data.get('keywords') or '')
        # Update only columns explicitly handled by this PATCH. A full model save can
        # write unrelated legacy columns and fail when the deployed legacy schema differs.
        field_map = {
            'name': 'product_name', 'code': 'code', 'subtitle': 'subtitle', 'brand': 'brand',
            'set_contains': 'set_contains', 'price': 'product_price', 'mrp': 'mrp',
            'discount': 'product_discount', 'category_id': 'category_id',
            'subcategory_id': 'subcategory_id', 'no_discount_banner': 'no_discount_banner',
            'disable_variants': 'disable_variants', 'visible': 'view', 'highlight': 'highlight',
            'minimum_buying_quantity': 'moq', 'minimum_buying_count': 'moq',
            'stock': 'stock', 'color': 'color', 'gst_applicable': 'gst_applicable',
            'gst_percentage': 'gst_percentage', 'gst_price': 'gst_price',
            'description': 'product_description', 'keywords': 'product_keywords',
            'product_details': 'product_details', 'additional_details': 'additional_details',
        }
        update_fields = {field_map[key] for key in data.keys() if key in field_map}
        if 'description' in data and 'product_details' not in data:
            update_fields.add('product_details')
        if 'keywords' in data and 'additional_details' not in data:
            update_fields.add('additional_details')
        if update_fields:
            # Execute a targeted UPDATE against the known legacy table, bypassing model
            # save hooks and avoiding writes to unrelated legacy columns.
            try:
                row.save(update_fields=sorted(update_fields))
            except Exception as orm_exc:
                # Some deployed legacy schemas reject ORM-generated updates. Retry using
                # an explicit UPDATE over the inspected zg_product column list.
                try:
                    db_columns = {
                        'product_name': 'product_name', 'code': 'code', 'subtitle': 'subtitle', 'brand': 'brand',
                        'set_contains': 'set_contains', 'product_price': 'product_price', 'mrp': 'mrp',
                        'product_discount': 'product_discount', 'category_id': 'category_id',
                        'subcategory_id': 'subcategory_id', 'no_discount_banner': 'no_discount_banner',
                        'disable_variants': 'disable_variants', 'view': 'view', 'highlight': 'highlight', 'moq': 'moq',
                        'stock': 'stock', 'color': 'color', 'gst_applicable': 'gst_applicable',
                        'gst_percentage': 'gst_percentage', 'gst_price': 'gst_price',
                        'product_description': 'product_description', 'product_keywords': 'product_keywords',
                        'product_details': 'product_details', 'additional_details': 'additional_details',
                    }
                    values_to_update = []
                    assignments = []
                    for field_name in sorted(update_fields):
                        if field_name not in db_columns:
                            continue
                        assignments.append(f"{db_columns[field_name]} = %s")
                        values_to_update.append(getattr(row, field_name))
                    if assignments:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                f"UPDATE zg_product SET {', '.join(assignments)} WHERE product_id = %s",
                                [*values_to_update, pid],
                            )
                            if cursor.rowcount != 1:
                                return Response({'detail': 'Product update did not affect exactly one record.'}, status=409)
                except Exception as sql_exc:
                    log_db_error('Product PATCH ORM and SQL save', sql_exc)
                    return Response({'detail': 'Product changes could not be saved against the current database schema. Check the sanitized server log for the failure category.'}, status=503)
        if discount_banners is not None:
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute('DELETE FROM zg_discount_banners WHERE product_id = %s', [pid])
                        for image_path in discount_banners:
                            cursor.execute('INSERT INTO zg_discount_banners (product_id, image_path) VALUES (%s, %s)', [pid, image_path])
            except Exception as exc:
                log_db_error('Product discount banner update', exc)
                return Response({'detail': 'Product fields saved, but discount banners could not be updated; reload and retry'}, status=503)
        return Response({'id': row.product_id, 'name': row.product_name, 'code': row.code,
            'price': str(row.product_price), 'category_id': row.category_id, 'subcategory_id': row.subcategory_id,
            'subtitle': getattr(row, 'subtitle', '') or '', 'brand': getattr(row, 'brand', '') or '',
            'discount_banners': discount_banners if discount_banners is not None else [], 'set_contains': self._parse_set_contains(getattr(row, 'set_contains', None)),
            'no_discount_banner': row.no_discount_banner if row.no_discount_banner in ('Y', 'N') else 'N',
            'disable_variants': row.disable_variants if row.disable_variants in ('Y', 'N') else 'N',
            **self._minimum_purchase_fields_out(row)})

    class _DependencyCheckFailed(Exception):
        pass

    @staticmethod
    def _delete_blocker(pid, variant_ids):
        """Message explaining why this product must not be deleted, or None when nothing protects it.

        order history is checked by the caller. zg_product's only database foreign key is the discount
        banner table, so customer carts and inventory history are checked here explicitly: deleting a
        product (or its variants) that they reference would silently orphan those records."""
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM a_cart WHERE product_id = %s', [pid])
                cart_count = cursor.fetchone()[0]
                if not cart_count and variant_ids:
                    marks = ','.join(['%s'] * len(variant_ids))
                    cursor.execute('SELECT COUNT(*) FROM a_cart WHERE variant_id IN (' + marks + ')', list(variant_ids))
                    cart_count = cursor.fetchone()[0]
        except Exception as exc:
            log_db_error('Product cart-dependency check', exc)
            raise ProductCRUDView._DependencyCheckFailed()
        if cart_count:
            return 'This product is present in customer carts and cannot be permanently deleted. Set Visibility to Hidden to archive it.'
        if variant_ids and StockLog.objects.filter(variant_id__in=variant_ids).exists():
            return 'This product has inventory (stock adjustment) history and cannot be permanently deleted. Set Visibility to Hidden to archive it.'
        return None

    def delete(self, request):
        try: pid = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError): return Response({'id': 'Valid product id required'}, status=400)
        try:
            with transaction.atomic():
                # Lock this one product row and re-check every reference under the lock, so a concurrent
                # order, cart add or edit cannot slip in between the check and the delete.
                row = Product.objects.select_for_update().filter(pk=pid).first()
                if not row: return Response({'detail': 'Product not found'}, status=404)
                variant_ids = list(Variant.objects.filter(product_id=pid).values_list('variant_id', flat=True))
                # Admin-confirmed permanent deletion: clean live catalogue/cart dependencies, preserve order and stock history.
                with connection.cursor() as cursor:
                    cursor.execute('DELETE FROM a_cart WHERE product_id = %s', [pid])
                    if variant_ids:
                        marks = ','.join(['%s'] * len(variant_ids))
                        cursor.execute('DELETE FROM a_cart WHERE variant_id IN (' + marks + ')', list(variant_ids))
                    cursor.execute('DELETE FROM zg_discount_banners WHERE product_id = %s', [pid])
                    cursor.execute('DELETE FROM zg_favorites WHERE product_id = %s', [pid])
                ProductImage.objects.filter(product_id=pid).delete()
                Variant.objects.filter(product_id=pid).delete()
                row.delete()
        except self._DependencyCheckFailed:
            return Response({'detail': 'Could not verify customer-cart dependencies; deletion was not performed.'}, status=503)
        except IntegrityError:
            return Response({'detail': 'Product is still referenced by another record and cannot be deleted. Hide it instead.'}, status=409)
        except Exception as exc:
            log_db_error('Product delete', exc)
            return Response({'detail': 'Product deletion failed because of a database constraint. No partial deletion was committed.'}, status=500)
        return Response(status=204)

class VariantCRUDView(APIView):
    required_resource = "catalogue"
    permission_classes = [AdminRolePermission]
    # Every key PATCH understands (plus the identifier). Anything else is rejected, never silently ignored.
    EDITABLE_FIELDS = frozenset({'id', 'product_id', 'name', 'price', 'variant_price', 'mrp', 'gst_price',
                                 'quantity', 'discount', 'gst', 'minimum_buying_count'})

    def get(self, request):
        # ?id=<variant id> returns that one saved record (read straight from the database, never from a list
        # the browser already holds) so View and Edit always show what is really stored.
        raw_id = request.query_params.get("id")
        if raw_id not in (None, ""):
            try:
                vid = int(raw_id)
            except (ValueError, TypeError):
                return Response({"id": "Valid variant id required"}, status=400)
            row = Variant.objects.filter(pk=vid).first()
            if not row:
                return Response({"detail": "Variant not found"}, status=404)
            return Response(self._list_row(row, self._product_names([row.product_id]),
                                           self._in_use_map([row.variant_id])))
        qs = Variant.objects.order_by("variant_id")
        if request.query_params.get("product_id"):
            qs = qs.filter(product_id=request.query_params["product_id"])
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            size = min(100, max(1, int(request.query_params.get("page_size", 20))))
        except (ValueError, TypeError):
            return Response({"detail": "Invalid pagination"}, status=400)
        page_rows = list(qs[(page-1)*size:page*size])
        in_use = self._in_use_map([x.variant_id for x in page_rows])
        names = self._product_names([x.product_id for x in page_rows])
        return Response({"count": qs.count(), "page": page, "page_size": size,
                         "results": [self._list_row(x, names, in_use) for x in page_rows]})

    @staticmethod
    def _list_row(x, product_names, in_use):
        return {"id": x.variant_id, "product_id": x.product_id, "product_name": product_names.get(x.product_id),
                "name": x.variant_name,
                "price": str(x.variant_price), "mrp": str(x.mrp), "quantity": x.quantity,
                "discount": x.disc, "gst": x.gst, "gst_price": str(x.gst_price),
                "minimum_buying_count": x.minimum_buying_count,
                # Informational only: which records still refer to this variant ("" = none). It never blocks
                # Edit or Delete; deleting a referenced variant is handled by DELETE (see delete()).
                "in_use": in_use.get(x.variant_id, "")}

    @staticmethod
    def _product_names(product_ids):
        """{product_id: product name} for the parent-product column. A failed lookup only leaves names empty."""
        ids = sorted({pid for pid in product_ids if pid is not None})
        if not ids:
            return {}
        try:
            return dict(Product.objects.filter(pk__in=ids).values_list("product_id", "product_name"))
        except Exception as exc:
            log_db_error("Variant parent-product name lookup", exc)
            return {}

    @staticmethod
    def _in_use_map(variant_ids):
        """{variant_id: "order history, customer carts, inventory history"} for variants that are referenced.

        Three batched queries per page. Any failure returns {} (no hint) and is logged: this is display-only
        information and must never break the list."""
        if not variant_ids:
            return {}
        try:
            found = {}
            for vid in OrderItem.objects.filter(variant_id__in=variant_ids).values_list("variant_id", flat=True):
                found.setdefault(vid, set()).add("order history")
            marks = ",".join(["%s"] * len(variant_ids))
            with connection.cursor() as cursor:
                cursor.execute("SELECT DISTINCT variant_id FROM a_cart WHERE variant_id IN (" + marks + ")", list(variant_ids))
                for (vid,) in cursor.fetchall():
                    found.setdefault(vid, set()).add("customer carts")
            for vid in StockLog.objects.filter(variant_id__in=variant_ids).values_list("variant_id", flat=True):
                found.setdefault(vid, set()).add("inventory history")
            order = ("order history", "customer carts", "inventory history")
            return {vid: ", ".join(x for x in order if x in kinds) for vid, kinds in found.items()}
        except Exception as exc:
            log_db_error("Variant in-use lookup", exc)
            return {}

    def post(self, request):
        try:
            pid = int(request.data.get('product_id'))
            raw_price = request.data.get('price')
            if raw_price is None or str(raw_price).strip() == '':
                raise ValueError('price is required')
            price = Decimal(str(raw_price))
            raw_mrp = request.data.get('mrp')
            mrp = price if raw_mrp is None or str(raw_mrp).strip() == '' else Decimal(str(raw_mrp))
            raw_qty = request.data.get('quantity')
            if raw_qty is None or str(raw_qty).strip() == '':
                raise ValueError('quantity is required')
            qty_decimal = Decimal(str(raw_qty))
            if not qty_decimal.is_finite() or qty_decimal != qty_decimal.to_integral_value():
                raise ValueError('quantity must be a whole number')
            qty = int(qty_decimal)
            gst_price = Decimal(str(request.data.get('gst_price', 0) or 0))
            discount = str(request.data.get('discount', '0'))
        except (ValueError, TypeError, InvalidOperation):
            return Response({'detail': 'Select a product and enter a valid price, MRP, quantity and GST amount.'}, status=400)
        name = clean_text(request.data.get('name', ''))
        gst = str(request.data.get('gst', 'N')).strip().upper()
        if not name:
            return Response({'name': 'Variant name is required.'}, status=400)
        # Each variant stores its own minimum purchase quantity; it is never copied from the product.
        # Default 1 only when the field is omitted; an explicit empty/invalid value is rejected before any write.
        minimum_buying_count = 1
        if 'minimum_buying_count' in request.data:
            try:
                minimum_buying_count = _validated_minimum_purchase_quantity(request.data['minimum_buying_count'])
            except ValueError as exc:
                return Response({'minimum_buying_count': str(exc)}, status=400)
        if not Product.objects.filter(pk=pid).exists():
            return Response({'product_id': 'Selected product was not found. Refresh the page and select it again.'}, status=400)
        if not all(value.is_finite() for value in (price, mrp, gst_price)) or min(price, mrp, gst_price) < 0 or qty < 0:
            return Response({'detail': 'Price, MRP, GST amount and quantity must be finite and non-negative.'}, status=400)
        if gst not in ('Y', 'N'):
            return Response({'gst': 'Choose Yes or No.'}, status=400)
        try:
            discount_value = Decimal(discount)
            if not discount_value.is_finite() or discount_value < 0 or discount_value > 100:
                return Response({'discount': 'Discount must be between 0 and 100.'}, status=400)
        except (InvalidOperation, ValueError):
            return Response({'discount': 'Enter a valid discount percentage.'}, status=400)
        try:
            row = Variant.objects.create(product_id=pid, variant_name=name, variant_price=price, mrp=mrp,
                disc=discount, quantity=qty, gst=gst, gst_price=gst_price,
                minimum_buying_count=minimum_buying_count)
        except IntegrityError:
            return Response({'detail': 'Variant could not be saved because a database constraint rejected the values.'}, status=400)
        except Exception as exc:
            log_db_error('Variant create', exc)
            return Response({'detail': 'Variant could not be saved. Check the Django server log for the underlying database error.'}, status=500)
        return Response({'id': row.variant_id, 'product_id': pid, 'name': row.variant_name,
            'price': str(row.variant_price), 'mrp': str(row.mrp), 'quantity': row.quantity,
            'discount': row.disc, 'gst': row.gst, 'gst_price': str(row.gst_price),
            'minimum_buying_count': row.minimum_buying_count}, status=201)

    def patch(self, request):
        try: vid = int(request.data.get('id'))
        except (ValueError, TypeError): return Response({'id': 'Valid variant id required'}, status=400)
        row = Variant.objects.filter(pk=vid).first()
        if not row: return Response({'detail': 'Variant not found'}, status=404)
        # A field this endpoint does not know used to be dropped while the request still reported success.
        unsupported = sorted(str(k) for k in request.data if k not in self.EDITABLE_FIELDS)
        if unsupported:
            return Response({'detail': 'Unsupported field(s): ' + ', '.join(unsupported) + '. Nothing was saved.'}, status=400)
        # A variant belongs to exactly one product. PATCH never moved it, so a different product_id used to be
        # ignored while the request still reported success; refuse it explicitly instead.
        if 'product_id' in request.data and request.data['product_id'] not in (None, ''):
            try: requested_product = int(request.data['product_id'])
            except (ValueError, TypeError): return Response({'product_id': 'Valid product id required'}, status=400)
            if requested_product != row.product_id:
                return Response({'product_id': 'A variant cannot be moved to another product. Create a new variant under that product instead.'}, status=400)
        if 'name' in request.data:
            if not clean_text(request.data['name']): return Response({'name': 'Name cannot be empty'}, status=400)
            row.variant_name = clean_text(request.data['name'])
        for field in ('price', 'variant_price', 'mrp', 'gst_price'):
            if field in request.data:
                target_field = 'variant_price' if field == 'price' else field
                try: value = Decimal(str(request.data[field]))
                except (ValueError, TypeError, InvalidOperation): return Response({field: 'Invalid decimal amount'}, status=400)
                if not value.is_finite() or value < 0:
                    return Response({field: 'Must be a finite non-negative amount'}, status=400)
                setattr(row, target_field, value)
        if 'quantity' in request.data:
            try: quantity_value = Decimal(str(request.data['quantity']))
            except (ValueError, TypeError, InvalidOperation): return Response({'quantity': 'Must be an integer'}, status=400)
            if not quantity_value.is_finite() or quantity_value != quantity_value.to_integral_value():
                return Response({'quantity': 'Must be a finite whole number'}, status=400)
            row.quantity = int(quantity_value)
            if row.quantity < 0: return Response({'quantity': 'Must be non-negative'}, status=400)
        if 'discount' in request.data:
            try: discount_value = Decimal(str(request.data['discount']))
            except (ValueError, TypeError, InvalidOperation): return Response({'discount': 'Enter a valid discount percentage'}, status=400)
            if not discount_value.is_finite() or discount_value < 0 or discount_value > 100:
                return Response({'discount': 'Discount must be between 0 and 100'}, status=400)
            row.disc = str(discount_value)
        if 'gst' in request.data:
            gst_value = str(request.data['gst']).strip().upper()
            if gst_value not in ('Y', 'N'): return Response({'gst': 'Choose Yes or No'}, status=400)
            row.gst = gst_value
        # Updated only when explicitly sent; an omitted field keeps the stored value.
        if 'minimum_buying_count' in request.data:
            try:
                row.minimum_buying_count = _validated_minimum_purchase_quantity(request.data['minimum_buying_count'])
            except ValueError as exc:
                return Response({'minimum_buying_count': str(exc)}, status=400)
        # Write only the columns this request changes, on this one variant row.
        column_for_key = {'name': 'variant_name', 'price': 'variant_price', 'variant_price': 'variant_price',
                          'mrp': 'mrp', 'gst_price': 'gst_price', 'quantity': 'quantity', 'discount': 'disc',
                          'gst': 'gst', 'minimum_buying_count': 'minimum_buying_count'}
        update_fields = sorted({column_for_key[key] for key in request.data if key in column_for_key})
        if update_fields:
            try:
                row.save(update_fields=update_fields)
            except IntegrityError:
                return Response({'detail': 'Variant could not be saved because a database constraint rejected the values.'}, status=400)
            except Exception as exc:
                log_db_error('Variant update', exc)
                return Response({'detail': 'Variant could not be saved. Check the Django server log for the underlying database error.'}, status=500)
        return Response(self._payload(row))

    @staticmethod
    def _payload(row):
        # Same fields as GET and POST so the UI can refresh a row from any of the three.
        return {'id': row.variant_id, 'product_id': row.product_id, 'name': row.variant_name,
                'price': str(row.variant_price), 'mrp': str(row.mrp), 'quantity': row.quantity,
                'discount': row.disc, 'gst': row.gst, 'gst_price': str(row.gst_price),
                'minimum_buying_count': row.minimum_buying_count}

    @staticmethod
    def _release_references(row, request):
        """Clean up what refers to a variant that is about to be permanently deleted. Runs inside delete()'s
        transaction, so either everything below and the delete itself happen, or nothing does.

        zg_variant has NO database foreign keys (verified against the live schema), so nothing blocks the delete and
        each referencing table is handled explicitly:
          * a_cart (customer carts): the lines for this variant are removed. They cannot be bought any more and a
            cart line pointing at a missing variant would only render as a broken row in the customer app.
          * zg_order_items (order history): deliberately NOT modified. Every line keeps its own snapshot of the
            product name, variant name, quantity, price, discount and total, and the order's total lives on
            zg_checkout, so amounts and names stay exact. variant_id is left as the historical identifier (it is
            never reused: the column is a database identity) rather than rewritten to NULL, because NULL already
            means "no variant" to order readers. Known limit: until the pending GST-snapshot migration is applied
            the customer-facing GST statement is derived from the live variant row, so it cannot recompute GST
            for a line whose variant no longer exists.
          * zg_stock_log (inventory history): existing rows are never changed or removed (variant_id is NOT NULL
            there). When the variant has stock history, one zero-quantity entry is appended recording that and
            by whom it was deleted, so the history stays explainable once the variant row is gone.
        """
        vid = row.variant_id
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM a_cart WHERE variant_id=%s', [vid])
        if StockLog.objects.filter(variant_id=vid).exists():
            StockLog.objects.create(
                variant_id=vid, adjustment=0, created_at=timezone.now(),
                admin=str(getattr(request.user, 'username', None) or 'admin')[:100],
                reason='Variant deleted: "%s" (product ID %s). Earlier stock adjustments for this variant are kept.'
                       % (row.variant_name, row.product_id))

    def delete(self, request):
        try: vid = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError): return Response({'id': 'Valid variant id required'}, status=400)
        try:
            with transaction.atomic():
                # Lock this one variant row so a concurrent edit or delete of the same variant cannot interleave.
                # Only this row is ever deleted: the parent product and sibling variants are never touched.
                row = Variant.objects.select_for_update().filter(pk=vid).first()
                if not row: return Response({'detail': 'Variant not found'}, status=404)
                # Historical GST is currently recalculated from the live variant: the approved schema has no
                # per-order GST snapshot columns, and the snapshot migration remains pending. Deleting a variant
                # referenced by an order would therefore change old tax statements. Refuse only this unsafe case;
                # cart-only and stock-only variants remain deletable, with cart lines cleaned up and stock history kept.
                # No reference-based blocker: admin confirmation authorizes deletion. Historical rows are preserved.
                self._release_references(row, request)
                row.delete()
        except Exception as exc:
            log_db_error('Variant delete', exc)
            return Response({'detail': 'Variant could not be deleted. Nothing was removed; check the Django server log for the underlying database error.'}, status=500)
        return Response(status=204)

class ProductImageCRUDView(APIView):
    required_resource = "catalogue"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = ProductImage.objects.order_by("product_id", "image_id")
        if request.query_params.get("product_id"):
            qs = qs.filter(product_id=request.query_params["product_id"])
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            size = min(100, max(1, int(request.query_params.get("page_size", 20))))
        except (ValueError, TypeError):
            return Response({"detail": "Invalid pagination"}, status=400)
        return Response({"count": qs.count(), "page": page, "page_size": size, "results": [
            {"id": x.image_id, "product_id": x.product_id, "image_path": x.image_path, "main": x.main}
            for x in qs[(page-1)*size:page*size]]})

    def post(self, request):
        try: pid = int(request.data.get('product_id'))
        except (ValueError, TypeError): return Response({'product_id': 'Valid product id required'}, status=400)
        path = str(request.data.get('image_path', '')).strip()
        if not path or not Product.objects.filter(pk=pid).exists():
            return Response({'detail': 'Existing product and image_path are required'}, status=400)
        main = '1' if request.data.get('main') in (True, 1, '1', 'true') else '0'
        with transaction.atomic():
            if main == '1': ProductImage.objects.filter(product_id=pid).update(main='0')
            row = ProductImage.objects.create(product_id=pid, image_path=path, main=main)
        return Response({'id': row.image_id, 'product_id': pid, 'image_path': row.image_path, 'main': row.main}, status=201)

    def delete(self, request):
        try: iid = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError): return Response({'id': 'Valid image id required'}, status=400)
        row = ProductImage.objects.filter(pk=iid).first()
        if not row: return Response({'detail': 'Image not found'}, status=404)
        row.delete()
        return Response(status=204)

CUSTOMER_FIELD_MAP = {
    'full_name': 'fullname', 'shop_name': 'shop_name', 'email': 'email', 'phone': 'phone', 'address': 'address',
    'city': 'city', 'status': 'status', 'gst': 'gst', 'gst_type': 'gst_type', 'gst_number': 'gst_number', 'gst_percentage': 'gst_percentage', 'delivery_charges': 'delivery_charges',
    'vip_discount': 'vip_discount', 'vip_percentage': 'vip_percentage', 'store_maped': 'store_maped',
    'warehouse_id': 'warehouse_id', 'color_code': 'color_code', 'category_id': 'category_id',
    'profile_picture': 'profile_picture',
}
CUSTOMER_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
CUSTOMER_PHONE_RE = re.compile(r'^[0-9+()\-\s]{6,20}$')
CUSTOMER_USERNAME_RE = re.compile(r'^[A-Za-z0-9_.@-]{3,100}$')
CUSTOMER_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
GST_NUMBER_LENGTH = 15  # the single GST Number rule: exactly this many characters (see _clean_customer)
CUSTOMER_TEXT_LIMITS = {'full_name': 255, 'shop_name': 255, 'email': 255, 'city': 255, 'color_code': 20, 'profile_picture': 255}
def _clean_customer(data, instance=None):
    """Validate the supplied customer fields only. Returns ({model_field: value}, {api_field: message})."""
    clean, errors = {}, {}
    for key in CUSTOMER_FIELD_MAP:
        if key not in data:
            continue
        raw = data[key]
        value = raw if key == 'gst_number' else (raw.strip() if isinstance(raw, str) else raw)
        if key in CUSTOMER_TEXT_LIMITS and value not in (None, '') and len(str(value)) > CUSTOMER_TEXT_LIMITS[key]:
            errors[key] = 'Must be at most %d characters.' % CUSTOMER_TEXT_LIMITS[key]
            continue
        if key == 'full_name':
            if not value:
                errors[key] = 'Customer name is required.'
                continue
        elif key == 'email':
            value, email_error = clean_email(value, required=True)
            if email_error:
                errors[key] = email_error
                continue
            duplicates = LegacyUser.objects.filter(email__iexact=value)
            if instance is not None:
                duplicates = duplicates.exclude(pk=instance.pk)
            if duplicates.exists():
                errors[key] = 'This email address is already used by another customer.'
                continue
        elif key == 'phone':
            value, phone_error = clean_indian_mobile(value, required=False)
            if phone_error:
                errors[key] = phone_error
                continue
            value = value or None
        elif key == 'status':
            value = str(value or '').upper()
            if value not in ('ACTIVE', 'INACTIVE', 'SUSPENDED'):
                errors[key] = 'Use ACTIVE, INACTIVE or SUSPENDED.'
                continue
        elif key in ('gst', 'vip_discount', 'store_maped'):
            value = str(value or '').upper()
            if value not in ('Y', 'N'):
                errors[key] = 'Use Y or N.'
                continue
        elif key == 'gst_type':
            value = str(value).upper() if value else None
            if value not in (None, 'REGULAR', 'COMPOUND'):
                errors[key] = 'Use REGULAR or COMPOUND.'
                continue
        elif key == 'gst_number':
            # The only rule: a nonempty value must have exactly 15 characters; no format checks or registration dependency.
            value = '' if value is None else str(value)
            if value and len(value) != GST_NUMBER_LENGTH:
                errors[key] = 'GST Number must contain exactly 15 characters.'
                continue
            value = value or None
        elif key == 'gst_percentage':
            try:
                value = Decimal(str(value)) if value not in (None, '') else None
            except (InvalidOperation, ValueError):
                errors[key] = 'Enter a valid GST percentage.'
                continue
            if value is not None and (not value.is_finite() or value < 0 or value > 100):
                errors[key] = 'GST percentage must be between 0 and 100.'
                continue
        elif key in ('vip_percentage', 'delivery_charges'):
            try:
                value = Decimal(str(value)) if value not in (None, '') else Decimal('0')
            except InvalidOperation:
                errors[key] = 'Enter a valid number.'
                continue
            limit = Decimal('100') if key == 'vip_percentage' else Decimal('99999999.99')
            if value < 0 or value > limit:
                errors[key] = 'Must be between 0 and %s.' % limit
                continue
        elif key == 'warehouse_id':
            if value in (None, ''):
                value = None
            else:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    errors[key] = 'Choose a valid warehouse.'
                    continue
                if not Warehouse.objects.filter(pk=value).exists():
                    errors[key] = 'Selected warehouse does not exist.'
                    continue
        elif key == 'category_id':
            if value in (None, ''):
                value = None
            else:
                value = str(value)
                if not value.isdigit() or not Category.objects.filter(pk=int(value)).exists():
                    errors[key] = 'Selected shop category does not exist.'
                    continue
        elif key == 'color_code':
            if value and not CUSTOMER_COLOR_RE.match(str(value)):
                errors[key] = 'Use a hex colour such as #33FF57.'
                continue
            value = value or None
        elif key in ('shop_name', 'address', 'city', 'profile_picture'):
            value = value or None
        clean[CUSTOMER_FIELD_MAP[key]] = value
    return clean, errors


def _customer_out(x, warehouse_names, request=None):
    return {
        'id': x.id, 'username': x.username, 'full_name': x.fullname, 'email': x.email,
        'phone': x.phone, 'shop_name': x.shop_name, 'status': x.status, 'city': x.city,
        'address': x.address, 'gst': x.gst, 'gst_type': x.gst_type, 'gst_number': x.gst_number, 'gst_percentage': str(x.gst_percentage) if x.gst_percentage is not None else '',
        'delivery_charges': str(x.delivery_charges or 0), 'vip_discount': x.vip_discount,
        'vip_percentage': str(x.vip_percentage or 0), 'store_maped': x.store_maped,
        'category_id': x.category_id, 'color_code': x.color_code,
        'warehouse_id': x.warehouse_id, 'warehouse_name': warehouse_names.get(x.warehouse_id),
        'profile_picture': x.profile_picture, 'profile_url': _image_url(x.profile_picture, request),
        'created_at': x.created_at,
    }


class CustomerCRUDView(APIView):
    required_resource = "customers"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        params = request.query_params
        qs = LegacyUser.objects.order_by('id')
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(fullname__icontains=search) | Q(email__icontains=search) | Q(shop_name__icontains=search) | Q(phone__icontains=search))
        vip = params.get('vip', '').strip().upper()
        if vip in ('Y', 'N'):
            qs = qs.filter(vip_discount=vip)
        color = params.get('color', '').strip()
        if color:
            qs = qs.filter(color_code=color)
        warehouse = params.get('warehouse_id', '').strip()
        if warehouse:
            if not warehouse.isdigit():
                return Response({'detail': 'warehouse_id must be a number'}, status=400)
            qs = qs.filter(warehouse_id=int(warehouse))
        offer = params.get('offer_id', '').strip()
        if offer:
            if not offer.isdigit():
                return Response({'detail': 'offer_id must be a number'}, status=400)
            qs = qs.filter(id__in=AdvancePayAllocation.objects.filter(offer_id=int(offer)).values('user_id'))
        try:
            page = max(1, int(params.get('page', 1)))
            size = min(100, max(1, int(params.get('page_size', 20))))
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid pagination'}, status=400)
        warehouses = list(Warehouse.objects.order_by('warehouse_name').values('warehouse_id', 'warehouse_name'))
        names = {w['warehouse_id']: w['warehouse_name'] for w in warehouses}
        colors = sorted(set(LegacyUser.objects.exclude(color_code__isnull=True).exclude(color_code='').values_list('color_code', flat=True)))
        offers = list(AdvancePayOffer.objects.order_by('offer_name').values('id', 'offer_name'))
        return Response({'count': qs.count(), 'page': page, 'page_size': size,
                         'results': [_customer_out(x, names, request) for x in qs[(page - 1) * size:page * size]],
                         'filters': {'colors': colors,
                                     'warehouses': [{'id': w['warehouse_id'], 'name': w['warehouse_name']} for w in warehouses],
                                     'offers': [{'id': o['id'], 'name': o['offer_name']} for o in offers]},
                         'shop_categories': [{'id': c['category_id'], 'name': c['category_name']} for c in Category.objects.order_by('category_name').values('category_id', 'category_name')]})

    def post(self, request):
        data = request.data
        errors = {}
        username = str(data.get('username', '')).strip()
        if not CUSTOMER_USERNAME_RE.match(username):
            errors['username'] = 'Use 3-100 letters, digits or . _ @ - characters.'
        elif LegacyUser.objects.filter(username__iexact=username).exists():
            errors['username'] = 'This username is already taken.'
        password = str(data.get('password', ''))
        if len(password) < 10:
            errors['password'] = 'Password must be at least 10 characters.'
        for required in ('email', 'full_name'):
            if required not in data:
                errors[required] = 'This field is required.'
        clean, field_errors = _clean_customer(data)
        errors.update(field_errors)
        if errors:
            return Response({'detail': ' '.join(errors.values()), 'errors': errors}, status=400)
        defaults = {'status': 'ACTIVE', 'gst': 'N', 'vip_discount': 'N', 'store_maped': 'N',
                    'vip_percentage': Decimal('0'), 'delivery_charges': Decimal('0')}
        for field, value in defaults.items():
            clean.setdefault(field, value)
        now = timezone.now()
        try:
            with transaction.atomic():
                row = LegacyUser.objects.create(username=username, password=hash_password(password), token='',
                                                latitude='', longitude='', created_at=now, updated_at=now, **clean)
        except IntegrityError:
            return Response({'detail': 'Username or email already exists.'}, status=409)
        names = dict(Warehouse.objects.values_list('warehouse_id', 'warehouse_name'))
        return Response(_customer_out(row, names, request), status=201)

    def patch(self, request):
        try:
            uid = int(request.data.get('id'))
        except (ValueError, TypeError):
            return Response({'id': 'Valid customer id required'}, status=400)
        row = LegacyUser.objects.filter(pk=uid).first()
        if not row:
            return Response({'detail': 'Customer not found'}, status=404)
        if getattr(request.user, 'role', None) == 'SALESMAN':
            safe_fields = {'id', 'full_name', 'shop_name', 'email', 'phone', 'address', 'city'}
            if set(request.data.keys()) - safe_fields:
                return Response({'detail': 'Salesmen may edit contact/shop details only'}, status=403)
        clean, errors = _clean_customer(request.data, instance=row)
        if errors:
            return Response({'detail': ' '.join(errors.values()), 'errors': errors}, status=400)
        if not clean:
            return Response({'detail': 'No editable fields supplied'}, status=400)
        for field, value in clean.items():
            setattr(row, field, value)
        row.updated_at = timezone.now()
        try:
            row.save(update_fields=list(clean) + ['updated_at'])
        except IntegrityError:
            return Response({'detail': 'Email already exists.'}, status=409)
        names = dict(Warehouse.objects.values_list('warehouse_id', 'warehouse_name'))
        return Response(_customer_out(row, names, request), status=200)
    def delete(self, request):
        raw_uid = request.query_params.get('id')
        if raw_uid in (None, ''):
            raw_uid = request.data.get('id')
        try:
            uid = int(raw_uid)
        except (ValueError, TypeError):
            return Response({'id': 'Valid customer id required'}, status=400)
        row = LegacyUser.objects.filter(pk=uid).first()
        if not row:
            return Response({'detail': 'Customer not found'}, status=404)
        # Legacy customer references are not all represented as Django foreign keys.
        # Preserve those records by deactivating customers that are still referenced.
        has_orders = Checkout.objects.filter(email=row.email).exists()
        has_advance_payments = AdvancePayAllocation.objects.filter(user_id=uid).exists()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM a_cart WHERE username=%s', [row.username])
                cart_count = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM zg_favorites WHERE user_id=%s', [row.username])
                favorite_count = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM zg_target_assignments WHERE user_id=%s', [uid])
                target_count = cursor.fetchone()[0]
        except Exception:
            return Response({'detail': 'Could not verify customer dependencies; no changes were made'}, status=503)
        if has_orders or has_advance_payments or cart_count or favorite_count or target_count:
            if row.status != 'INACTIVE':
                row.status = 'INACTIVE'
                row.updated_at = timezone.now()
                row.save(update_fields=['status', 'updated_at'])
            reasons = []
            if has_orders: reasons.append('order history')
            if has_advance_payments: reasons.append('advance-payment records')
            if cart_count: reasons.append('cart items')
            if favorite_count: reasons.append('favourites')
            if target_count: reasons.append('target assignments')
            return Response({
                'detail': 'Customer was deactivated instead of deleted to preserve linked records (' + ', '.join(reasons) + ').',
                'action': 'deactivated', 'id': row.id, 'status': row.status,
            }, status=200)
        try:
            with transaction.atomic():
                row.delete()
        except IntegrityError:
            return Response({'detail': 'Customer is still referenced by another record and was not deleted. Try deactivating it instead.', 'code': 'customer_referenced'}, status=409)
        return Response(status=204)


class OrderAdminCRUDView(APIView):
    required_resource = "orders"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        if request.query_params.get("id"):
            try:
                oid = int(request.query_params["id"])
            except (ValueError, TypeError):
                return Response({"id": "Valid order id required"}, status=400)
            order = Checkout.objects.filter(pk=oid).first()
            if not order:
                return Response({"detail": "Order not found"}, status=404)
            items = OrderItem.objects.filter(order_id=oid).order_by("item_id")
            return Response({"order": {"id": order.order_id, "customer": order.full_name, "email": order.email,
                "phone": order.phone, "address": order.address, "total_amount": str(order.total_amount),
                "status": order.status, "order_date": order.order_date, "payment_method": order.payment_method},
                "items": [{"id": x.item_id, "product_id": x.product_id, "variant_id": x.variant_id,
                    "product_name": x.product_name, "variant_name": x.variant_name, "quantity": x.quantity,
                    "price": str(x.price), "discount": str(x.discount), "total_price": str(x.total_price)} for x in items]})
        qs = Checkout.objects.order_by('-order_date')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search) | Q(status__icontains=search) | Q(phone__icontains=search))
        if request.query_params.get('status'): qs = qs.filter(status=request.query_params['status'])
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError): return Response({'detail': 'Invalid pagination'}, status=400)
        rows = list(qs[(page-1)*size:page*size])
        return Response({'count': qs.count(), 'page': page, 'page_size': size, 'results': [
            {'id': x.order_id, 'customer': x.full_name, 'email': x.email, 'phone': x.phone,
             'total_amount': str(x.total_amount), 'status': x.status, 'order_date': x.order_date,
             'payment_method': x.payment_method} for x in rows]})

    def post(self, request):
        """Create an admin-entered order using prices read from the existing product tables."""
        if getattr(request.user, "role", None) not in {"SUPER_ADMIN", "ADMIN"}:
            return Response({"detail": "Only administrators can create orders."}, status=403)
        data = request.data
        limits = {"full_name": 255, "email": 255, "phone": 20, "address": 255, "city": 100,
                  "state": 100, "postal_code": 20, "country": 100, "payment_method": 255}
        values = {}
        for field, max_len in limits.items():
            raw = data.get(field, "India" if field == "country" else "COD" if field == "payment_method" else "")
            value = str(raw or "").strip()
            if len(value) > max_len:
                return Response({field: f"Must be at most {max_len} characters."}, status=400)
            values[field] = value
        if not values["full_name"] or not values["email"] or not values["phone"] or not values["address"]:
            return Response({"detail": "Customer name, email, phone and delivery address are required."}, status=400)
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", values["email"]):
            return Response({"email": "Enter a valid e-mail address."}, status=400)
        raw_items = data.get("items")
        if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 100:
            return Response({"items": "Provide between 1 and 100 order items."}, status=400)
        parsed, seen = [], set()
        subtotal = Decimal("0")
        for entry in raw_items:
            if not isinstance(entry, dict):
                return Response({"items": "Each item must be an object."}, status=400)
            try:
                product_id = int(entry.get("product_id"))
                quantity_value = Decimal(str(entry.get("quantity")))
                variant_id = int(entry["variant_id"]) if entry.get("variant_id") not in (None, "") else None
            except (TypeError, ValueError, InvalidOperation):
                return Response({"items": "Each item needs a valid product, optional variant, and whole quantity."}, status=400)
            if product_id <= 0 or not quantity_value.is_finite() or quantity_value != quantity_value.to_integral_value() or quantity_value <= 0:
                return Response({"items": "Product IDs must be positive and quantity must be a positive whole number."}, status=400)
            key = (product_id, variant_id)
            if key in seen:
                return Response({"items": "Remove duplicate product/variant lines before submitting."}, status=400)
            seen.add(key)
            product = Product.objects.filter(pk=product_id).first()
            if product is None:
                return Response({"items": f"Product {product_id} was not found."}, status=400)
            # Variant ownership and price are validated together below.
            if variant_id is not None:
                variant = Variant.objects.filter(pk=variant_id, product_id=product_id).first()
                if variant is None:
                    return Response({'items': f'Variant {variant_id} does not belong to product {product_id}.'}, status=400)
                price, variant_name = Decimal(str(variant.variant_price)), variant.variant_name
            else:
                if Variant.objects.filter(product_id=product_id).exists():
                    return Response({'items': f'Choose a variant for product {product_id}.'}, status=400)
                price, variant_name = Decimal(str(product.product_price)), ''
            line_total = (price * quantity_value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            subtotal += line_total
            parsed.append({"product_id": product_id, "variant_id": variant_id, "product_name": product.product_name,
                           "variant_name": variant_name, "quantity": int(quantity_value), "price": price,
                           "discount": Decimal("0.00"), "total_price": line_total})
        total = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        try:
            with transaction.atomic():
                order = Checkout.objects.create(
                    user="", full_name=values["full_name"], email=values["email"], phone=values["phone"],
                    address=values["address"], city=values["city"], state=values["state"],
                    postal_code=values["postal_code"], country=values["country"], total_amount=total,
                    order_date=timezone.now(), status="Placed", delivery_boy_id=None, view="n",
                    payment_method=values["payment_method"], shipping_charge="0", cod_charge=Decimal("0.00"))
                for item in parsed:
                    OrderItem.objects.create(order_id=order.order_id, **item)
                OrderStatusHistory.objects.create(order_id=order.order_id, status="Placed",
                                                  changed_at=timezone.now(), message="Created from StokIt admin.")
        except Exception as exc:
            log_db_error("Admin order create", exc)
            return Response({"detail": "Order could not be created against the current legacy schema."}, status=400)
        return Response({"id": order.order_id, "status": order.status, "total_amount": str(total),
                         "message": "Order created."}, status=201)
    def patch(self, request):
        try: oid = int(request.data.get('id'))
        except (ValueError, TypeError): return Response({'id': 'Valid order id required'}, status=400)
        row = Checkout.objects.filter(pk=oid).first()
        if not row: return Response({'detail': 'Order not found'}, status=404)
        value = str(request.data.get('status', '')).strip()
        allowed_by_role = {
            'SUPER_ADMIN': {'Placed', 'Processing', 'Shipped', 'Out for Delivery', 'Delivered', 'Fulfilled', 'Cancelled'},
            'ADMIN': {'Placed', 'Processing', 'Shipped', 'Out for Delivery', 'Delivered', 'Fulfilled', 'Cancelled'},
            'SALESMAN': {'Placed', 'Processing'},
            'WAREHOUSE_STAFF': {'Processing', 'Shipped'},
            'DELIVERY_BOY': {'Out for Delivery', 'Delivered'},
        }
        if value not in allowed_by_role.get(getattr(request.user, 'role', None), set()):
            return Response({'status': 'This role cannot set the requested order status'}, status=403)
        row.status = value
        row.save(update_fields=['status'])
        return Response({'id': row.order_id, 'status': row.status})
