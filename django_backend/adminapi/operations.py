import re
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction, connection
from django.utils import timezone
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView
from .permissions import AdminRolePermission
from .field_validation import clean_email, clean_indian_mobile, clean_text
from .db_errors import log_db_error
from accounts.hashers import hash_password
from .image_urls import image_url
from legacydb import monthly_credit as mc
from legacydb.models import Slider, Notification, LegacyUser, Category, Warehouse, Salesman, DeliveryBoy, Variant, StockLog, Checkout, AdvancePayOffer, AdvancePayAllocation, Target, TargetAssignment, TargetAchievement

MIN_ADVANCE_OFFER_MONTHS = 12

def _validated_advance_duration(raw):
    """Accept integer durations >= 12 without silently truncating decimals."""
    try:
        value = Decimal(str(raw).strip())
    except (ValueError, TypeError, InvalidOperation, AttributeError):
        return None
    if not value.is_finite() or value != value.to_integral_value() or value < MIN_ADVANCE_OFFER_MONTHS:
        return None
    return int(value)

class BaseAdminResource(APIView):
    permission_classes = [AdminRolePermission]
    required_resource = 'dashboard'
    def page(self, request, qs, serializer):
        try:
            page=max(1,int(request.query_params.get('page',1)))
            size=min(100,max(1,int(request.query_params.get('page_size',20))))
        except (ValueError,TypeError):
            return Response({'detail':'Invalid pagination'},status=400)
        return Response({'count':qs.count(),'page':page,'page_size':size,'results':[serializer(x) for x in qs[(page-1)*size:page*size]]})

class BannerAdminView(BaseAdminResource):
    required_resource='banners'
    def get(self,request):
        qs=Slider.objects.order_by('-slider_id')
        s=request.query_params.get('search','').strip()
        if s: qs=qs.filter(Q(text_content__icontains=s)|Q(styled_text__icontains=s)|Q(image_path__icontains=s))
        def serialize_banner(x):
            image_path = str(x.image_path or '').strip()
            return {'id': x.slider_id, 'image_path': image_path,
                    'image_url': image_url(image_path, request), 'text_content': x.text_content,
                    'styled_text': x.styled_text, 'styled_color': x.styled_color,
                    'background': x.back, 'text_content2': x.text_content2}
        return self.page(request, qs, serialize_banner)
    def post(self,request):
        raw_path=request.data.get('image_path','');path=raw_path.strip() if isinstance(raw_path,str) else ''
        if not path:return Response({'image_path':'Image path or uploaded URL is required'},status=400)
        x=Slider.objects.create(image_path=path,text_content=str(request.data.get('text_content','')),styled_text=str(request.data.get('styled_text','')),styled_color=str(request.data.get('styled_color','#000000')),back=str(request.data.get('background','#ffffff')),text_content2=str(request.data.get('text_content2','')))
        return Response({'id':x.slider_id,'image_path':x.image_path},status=201)
    def patch(self,request):
        try: rid=int(request.data.get('id'))
        except (ValueError,TypeError):return Response({'id':'Valid banner id required'},status=400)
        x=Slider.objects.filter(pk=rid).first()
        if not x:return Response({'detail':'Banner not found'},status=404)
        mapping={'image_path':'image_path','text_content':'text_content','styled_text':'styled_text','styled_color':'styled_color','background':'back','text_content2':'text_content2'}
        for key,field in mapping.items():
            if key not in request.data:continue
            value=request.data[key]
            if key=='image_path':
                # A non-string path must be rejected before anything is assigned or saved,
                # so the existing image stays intact.
                if not isinstance(value,str):return Response({'image_path':'Image path must be a string'},status=400)
                value=value.strip()
            elif value is None:value=''
            setattr(x,field,str(value))
        if not x.image_path:return Response({'image_path':'Required'},status=400)
        x.save();return Response({'id':x.slider_id,'image_path':x.image_path})
    def delete(self,request):
        try: rid=int(request.query_params.get('id',request.data.get('id')))
        except (ValueError,TypeError):return Response({'id':'Valid banner id required'},status=400)
        deleted,_=Slider.objects.filter(pk=rid).delete()
        return Response(status=204) if deleted else Response({'detail':'Banner not found'},status=404)

class NotificationAdminView(BaseAdminResource):
    required_resource='notifications'

    def get(self,request):
        qs=Notification.objects.order_by('-created_at','-id')
        s=request.query_params.get('search','').strip()
        if s:qs=qs.filter(Q(title__icontains=s)|Q(message__icontains=s)|Q(recipient_type__icontains=s))
        def serialize_page(rows):
            ids={x.customer_id for x in rows if x.customer_id}
            names=dict(LegacyUser.objects.filter(pk__in=ids).values_list('id','username')) if ids else {}
            return [{'id':x.id,'customer_id':x.customer_id,'customer_name':names.get(x.customer_id),'title':x.title,
                     'message':x.message,'sent_by':x.sent_by,'created_at':x.created_at,'is_read':x.is_read,
                     'read_at':x.read_at,'recipient_type':x.recipient_type} for x in rows]
        try:
            page=max(1,int(request.query_params.get('page',1)))
            size=min(100,max(1,int(request.query_params.get('page_size',20))))
        except (ValueError,TypeError):
            return Response({'detail':'Invalid pagination'},status=400)
        rows=list(qs[(page-1)*size:page*size])
        return Response({'count':qs.count(),'page':page,'page_size':size,'results':serialize_page(rows)})

    def post(self,request):
        title=str(request.data.get('title','')).strip(); message=str(request.data.get('message','')).strip()
        errors={}
        if not title:errors['title']='Title is required.'
        elif len(title)>255:errors['title']='Title must be at most 255 characters.'
        if not message:errors['message']='Message is required.'
        elif len(message)>5000:errors['message']='Message must be at most 5000 characters.'
        recipient=str(request.data.get('recipient_type','all')).strip().lower()
        cid=request.data.get('customer_id') or None
        if recipient not in ('all','selected'):
            errors['recipient_type']='Use all or selected.'
        elif recipient=='selected':
            try:
                cid=int(cid)
                if not LegacyUser.objects.filter(pk=cid).exists():errors['customer_id']='Selected customer does not exist.'
            except (ValueError,TypeError):
                errors['customer_id']='Choose a customer for a selected recipient.'
        else:
            cid=None
        if errors:return Response({'detail':' '.join(errors.values()),'errors':errors},status=400)
        x=Notification.objects.create(customer_id=cid,title=title,message=message,sent_by=getattr(request.user,'username','admin'),recipient_type=recipient,is_read=False,created_at=timezone.now())
        # Stored in the in-app notification table only: no push (Firebase) delivery is performed by this endpoint.
        return Response({'id':x.id,'title':x.title,'message':x.message,'recipient_type':x.recipient_type,'customer_id':x.customer_id,
                         'delivery':'stored','delivery_note':'Saved to the in-app notification list. Push delivery is not configured.'},status=201)

    def delete(self,request):
        try:rid=int(request.query_params.get('id',request.data.get('id')))
        except (ValueError,TypeError):return Response({'id':'Valid notification id required'},status=400)
        deleted,_=Notification.objects.filter(pk=rid).delete()
        return Response(status=204) if deleted else Response({'detail':'Notification not found'},status=404)

class WarehouseAdminView(BaseAdminResource):
    required_resource='warehouse'
    def get(self,request):
        qs=Warehouse.objects.order_by('warehouse_name')
        s=request.query_params.get('search','').strip()
        if s:qs=qs.filter(Q(warehouse_name__icontains=s)|Q(place__icontains=s)|Q(state__icontains=s))
        return self.page(request,qs,lambda x:{'id':x.warehouse_id,'name':x.warehouse_name,'address':x.address,'pincode':x.pincode,'state':x.state,'place':x.place,'latitude':x.latitude,'longitude':x.longitude})
    @staticmethod
    def _coordinate(value, field, minimum, maximum):
        if value is None or str(value).strip() == '':
            return None, None
        try:
            number = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError):
            return None, {field: 'Enter a valid numeric coordinate.'}
        if not number.is_finite() or number < Decimal(str(minimum)) or number > Decimal(str(maximum)):
            return None, {field: f'Enter a coordinate between {minimum} and {maximum}.'}
        if max(0, -number.as_tuple().exponent) > 8:
            return None, {field: 'Use no more than 8 decimal places.'}
        return number, None

    def post(self,request):
        name=clean_text(request.data.get('name',''))
        errors={}
        if not name: errors['name']='Warehouse name is required.'
        elif len(name)>100: errors['name']='Warehouse name must be 100 characters or fewer.'
        latitude, lat_error = self._coordinate(request.data.get('latitude'), 'latitude', -90, 90)
        longitude, lon_error = self._coordinate(request.data.get('longitude'), 'longitude', -180, 180)
        if lat_error: errors.update(lat_error)
        if lon_error: errors.update(lon_error)
        pincode=request.data.get('pincode')
        if pincode not in (None, '') and len(str(pincode).strip())>10:
            errors['pincode']='Pincode must be 10 characters or fewer.'
        if errors: return Response({'detail':' '.join(errors.values()),'errors':errors},status=400)
        x=Warehouse.objects.create(
            warehouse_name=name,
            address=request.data.get('address') or None,
            pincode=str(pincode).strip() if pincode not in (None, '') else None,
            state=request.data.get('state') or None,
            place=request.data.get('place') or None,
            latitude=latitude,
            longitude=longitude,
        )
        return Response({'id':x.warehouse_id,'name':x.warehouse_name},status=201)
    def patch(self,request):
        try:rid=int(request.data.get('id') or request.query_params.get('id'))
        except (ValueError,TypeError):return Response({'id':'Valid warehouse id required'},status=400)
        x=Warehouse.objects.filter(pk=rid).first()
        if not x:return Response({'detail':'Warehouse not found'},status=404)
        mapping={'name':'warehouse_name','address':'address','pincode':'pincode','state':'state','place':'place'}
        errors={}
        for key,field in mapping.items():
            if key in request.data:
                value=request.data[key]
                if key == 'name':
                    value=str(value or '').strip()
                    if not value: errors['name']='Warehouse name is required.'
                    elif len(value)>100: errors['name']='Warehouse name must be 100 characters or fewer.'
                if key == 'pincode' and value not in (None, '') and len(str(value).strip())>10:
                    errors['pincode']='Pincode must be 10 characters or fewer.'
                setattr(x,field,value or None)
        if 'latitude' in request.data:
            value, problem=self._coordinate(request.data.get('latitude'),'latitude',-90,90)
            if problem: errors.update(problem)
            else: x.latitude=value
        if 'longitude' in request.data:
            value, problem=self._coordinate(request.data.get('longitude'),'longitude',-180,180)
            if problem: errors.update(problem)
            else: x.longitude=value
        if errors:return Response({'detail':' '.join(errors.values()),'errors':errors},status=400)
        x.save();return Response({'id':x.warehouse_id,'name':x.warehouse_name})
    def delete(self,request):
        try: rid=int(request.query_params.get('id',request.data.get('id')))
        except (ValueError,TypeError): return Response({'id':'Valid warehouse id required'},status=400)
        row=Warehouse.objects.filter(pk=rid).first()
        if not row: return Response({'detail':'Warehouse not found'},status=404)
        # Check only known legacy relationship tables that actually exist in this
        # schema. Missing tables must not turn a valid DELETE into a 503, while
        # any discovered dependency blocks deletion (no cascade of business data).
        dependency_specs = (
            ('users', 'warehouse_id', 'customers'),
            ('warehouse_salesmen', 'warehouse_id', 'salesmen'),
            ('warehouse_delivery_boys', 'warehouse_id', 'delivery staff'),
        )
        try:
            with connection.cursor() as cursor:
                tables = set(connection.introspection.table_names(cursor))
                dependencies = []
                for table, column, label in dependency_specs:
                    if table not in tables:
                        continue
                    columns = {item.name for item in connection.introspection.get_table_description(cursor, table)}
                    if column not in columns:
                        continue
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}"=%s', [rid])
                    count = cursor.fetchone()[0]
                    if count:
                        dependencies.append(f'{count} {label} record(s)')
        except Exception:
            return Response({'detail':'Could not verify warehouse dependencies; deletion was not performed'},status=503)
        if dependencies:
            return Response({'detail':'Warehouse is still referenced by ' + ', '.join(dependencies) + '. Unassign these records before deleting.'},status=409)
        try:
            with transaction.atomic():
                row.delete()
        except Exception:
            return Response({'detail':'Warehouse deletion was blocked by a related record or database constraint; no deletion was completed.'},status=409)
        return Response(status=204)

class InventoryAdminView(BaseAdminResource):
    required_resource='inventory'
    def get(self,request):
        qs=Variant.objects.order_by('product_id','variant_id')
        if request.query_params.get('warehouse_id'):
            return Response({'detail':'Legacy variant stock is not warehouse-scoped; warehouse filter is unsupported by this schema'},status=400)
        s=request.query_params.get('search','').strip()
        if s:qs=qs.filter(Q(variant_name__icontains=s)|Q(product_id__icontains=s))
        return self.page(request,qs,lambda x:{'id':x.variant_id,'product_id':x.product_id,'variant':x.variant_name,'price':str(x.variant_price),'quantity':x.quantity,'category_id':x.category_id,'subcategory_id':x.subcategory_id})
    def patch(self,request):
        try:vid=int(request.data.get('id')); quantity=int(request.data.get('quantity'))
        except (ValueError,TypeError):return Response({'detail':'Valid id and integer quantity required'},status=400)
        if quantity<0:return Response({'quantity':'Must be non-negative'},status=400)
        reason=str(request.data.get('reason','')).strip()
        if not reason:return Response({'reason':'Required for stock audit'},status=400)
        with transaction.atomic():
            x=Variant.objects.select_for_update().filter(pk=vid).first()
            if not x:return Response({'detail':'Variant not found'},status=404)
            delta=quantity-int(x.quantity)
            if delta:
                x.quantity=quantity;x.save(update_fields=['quantity'])
                StockLog.objects.create(variant_id=vid,adjustment=delta,reason=reason,admin=getattr(request.user,'username','admin'),created_at=timezone.now())
        return Response({'id':x.variant_id,'quantity':x.quantity})

class StaffAdminView(BaseAdminResource):
    required_resource='staff'
    def get(self,request):
        kind=request.query_params.get('kind','salesmen')
        model=DeliveryBoy if kind=='delivery' else Salesman if kind=='salesmen' else None
        if model is None:return Response({'kind':'Use salesmen or delivery'},status=400)
        qs=model.objects.order_by('-id')
        s=request.query_params.get('search','').strip()
        if s:qs=qs.filter(Q(username__icontains=s)|Q(fullname__icontains=s)|Q(email__icontains=s))
        serializer=lambda x: ({'id':x.id,'username':x.username,'email':x.email,'full_name':x.fullname,'phone':x.phone,'address':x.address,'commission_rate':str(x.commission_rate),'target_sales':str(x.target_sales),'hire_date':x.hire_date} if kind=='salesmen' else {'id':x.id,'username':x.username,'email':x.email,'full_name':x.fullname,'phone':x.phone,'address':x.address})
        return self.page(request,qs,serializer)
    def post(self,request):
        kind=request.data.get('kind','salesmen')
        username=str(request.data.get('username','')).strip(); email=str(request.data.get('email','')).strip()
        name=str(request.data.get('full_name','')).strip(); password=str(request.data.get('password',''))
        if kind not in ('salesmen','delivery') or not username or not email or not name or len(password)<10:
            return Response({'detail':'kind, username, email, full_name and password (at least 10 characters) are required'},status=400)
        email, email_error = clean_email(email, required=True)
        phone, phone_error = clean_indian_mobile(request.data.get('phone', ''), required=True)
        field_errors = {}
        if email_error: field_errors['email'] = email_error
        if phone_error: field_errors['phone'] = phone_error
        if field_errors: return Response({'detail':'Please correct the highlighted fields.','errors':field_errors},status=400)
        model=DeliveryBoy if kind=='delivery' else Salesman
        values={'username':username,'email':email,'fullname':name,'password':hash_password(password),'phone':phone,'address':str(request.data.get('address','')).strip()}
        if kind=='delivery':values['paymentDate']='';values['token']='';values['api_token']=None;values['created_at']=timezone.now()
        else:
            try:values['commission_rate']=Decimal(str(request.data.get('commission_rate',0)));values['target_sales']=Decimal(str(request.data.get('target_sales',0)))
            except (ValueError,TypeError,InvalidOperation):return Response({'detail':'Invalid commission or target sales'},status=400)
            values['hire_date']=request.data.get('hire_date') or None;values['token']=None;values['api_token']=None;values['created_at']=timezone.now()
        if not values['phone']:return Response({'phone':'Required'},status=400)
        try:x=model.objects.create(**values)
        except Exception:return Response({'detail':'Could not create staff record; check duplicate username/email and legacy schema constraints'},status=400)
        return Response({'id':x.id,'username':x.username,'email':x.email,'full_name':x.fullname,'kind':kind},status=201)
    def patch(self,request):
        kind=request.data.get('kind','salesmen')
        try:rid=int(request.data.get('id'))
        except (ValueError,TypeError):return Response({'id':'Valid staff id required'},status=400)
        model=DeliveryBoy if kind=='delivery' else Salesman if kind=='salesmen' else None
        if model is None:return Response({'kind':'Use salesmen or delivery'},status=400)
        x=model.objects.filter(pk=rid).first()
        if not x:return Response({'detail':'Staff member not found'},status=404)
        mapping={'username':'username','email':'email','full_name':'fullname','phone':'phone','address':'address'}
        for key,field in mapping.items():
            if key in request.data:
                value=str(request.data[key]).strip()
                if key in ('username','email','full_name','phone') and not value:return Response({key:'Cannot be empty'},status=400)
                if key == 'email':
                    value, error = clean_email(value, required=True)
                    if error: return Response({'detail':'Please correct the highlighted fields.','errors':{'email':error}},status=400)
                if key == 'phone':
                    value, error = clean_indian_mobile(value, required=True)
                    if error: return Response({'detail':'Please correct the highlighted fields.','errors':{'phone':error}},status=400)
                setattr(x,field,value)
        if request.data.get('password'):
            if len(str(request.data['password']))<10:return Response({'password':'Minimum 10 characters'},status=400)
            x.password=hash_password(str(request.data['password']))
        if kind=='salesmen':
            for key in ('commission_rate','target_sales'):
                if key in request.data:
                    try:setattr(x,key,Decimal(str(request.data[key])))
                    except (ValueError,TypeError,InvalidOperation):return Response({key:'Invalid amount'},status=400)
            if 'hire_date' in request.data:x.hire_date=request.data['hire_date'] or None
        x.save();return Response({'id':x.id,'username':x.username,'email':x.email,'full_name':x.fullname,'kind':kind})
    def delete(self,request):
        kind=request.query_params.get('kind','salesmen')
        try: rid=int(request.query_params.get('id',request.data.get('id')))
        except (ValueError,TypeError): return Response({'id':'Valid staff id required'},status=400)
        model=DeliveryBoy if kind=='delivery' else Salesman if kind=='salesmen' else None
        if model is None: return Response({'kind':'Use salesmen or delivery'},status=400)
        if not model.objects.filter(pk=rid).exists(): return Response({'detail':'Staff member not found'},status=404)
        try:
            with connection.cursor() as cursor:
                if kind=='delivery':
                    cursor.execute('SELECT COUNT(*) FROM warehouse_delivery_boys WHERE delivery_boy_id=%s',[rid]); assigned=cursor.fetchone()[0]
                else:
                    cursor.execute('SELECT COUNT(*) FROM warehouse_salesmen WHERE salesman_id=%s',[rid]); assigned=cursor.fetchone()[0]
        except Exception:
            return Response({'detail':'Could not verify staff dependencies; deletion was not performed'},status=503)
        if assigned: return Response({'detail':'Staff member is assigned to a warehouse; unassign before deleting'},status=409)
        if kind=='delivery' and Checkout.objects.filter(delivery_boy_id=rid).exists():
            return Response({'detail':'Delivery personnel has order history/assignments and cannot be deleted'},status=409)
        model.objects.filter(pk=rid).delete()
        return Response(status=204)

class AdvancePaymentAdminView(BaseAdminResource):
    required_resource='advance_payments'

    def get(self, request):
        qs = AdvancePayOffer.objects.order_by('-created_at')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(offer_name__icontains=search) | Q(status__icontains=search))
        return self.page(request, qs, lambda x: {
            'id': x.id, 'offer_name': x.offer_name,
            'payment_amount': str(x.payment_amount),
            'bonus_percentage': str(x.bonus_percentage),
            'duration_months': x.duration_months,
            'monthly_bonus': str(mc.monthly_credit_release(x.payment_amount, x.bonus_percentage)),
            'total_credit': str(mc.total_credit(x.payment_amount, x.bonus_percentage, x.duration_months)),
            'benefit': str(mc.total_credit(x.payment_amount, x.bonus_percentage, x.duration_months)),
            'status': x.status, 'image_path': x.image_path,
        })

    def post(self, request):
        name = str(request.data.get('offer_name', '')).strip()
        try:
            amount = Decimal(str(request.data.get('payment_amount')))
            bonus = Decimal(str(request.data.get('bonus_percentage', 0)))
            months = _validated_advance_duration(request.data.get('duration_months'))
            if months is None:
                return Response({'duration_months': 'Duration must be at least 12 months.'}, status=400)
            credit = mc.total_credit(amount, bonus, months)
        except (ValueError, TypeError, InvalidOperation, mc.CreditConfigError):
            return Response({'detail': 'Valid payment amount, bonus percentage and duration are required'}, status=400)
        if not name or amount <= 0 or bonus < 0 or bonus > 100:
            return Response({'detail': 'Offer name, positive payment amount, bonus percentage from 0 to 100, and duration are required'}, status=400)
        status_value = str(request.data.get('status', 'ACTIVE')).upper()
        if status_value not in ('ACTIVE', 'INACTIVE'):
            return Response({'status': 'Use ACTIVE or INACTIVE'}, status=400)
        x = AdvancePayOffer.objects.create(offer_name=name, payment_amount=amount, bonus_percentage=bonus, duration_months=months, total_credit=credit, status=status_value, image_path=request.data.get('image_path') or None, created_at=timezone.now(), updated_at=timezone.now())
        return Response({'id': x.id, 'offer_name': x.offer_name, 'total_credit': str(credit), 'monthly_bonus': str(mc.monthly_credit_release(amount, bonus)), 'benefit': str(credit), 'status': x.status}, status=201)

    def patch(self, request):
        try:
            rid = int(request.data.get('id') or request.query_params.get('id'))
        except (ValueError, TypeError):
            return Response({'id': 'Valid offer id required'}, status=400)
        x = AdvancePayOffer.objects.filter(pk=rid).first()
        if not x:
            return Response({'detail': 'Offer not found'}, status=404)
        recalculate = any(key in request.data for key in ('payment_amount', 'bonus_percentage', 'duration_months'))
        for key, field in (('offer_name', 'offer_name'), ('payment_amount', 'payment_amount'), ('bonus_percentage', 'bonus_percentage'), ('duration_months', 'duration_months')):
            if key in request.data:
                try:
                    value = _validated_advance_duration(request.data[key]) if key == 'duration_months' else str(request.data[key]).strip() if key == 'offer_name' else Decimal(str(request.data[key]))
                except (ValueError, TypeError, InvalidOperation):
                    return Response({key: 'Invalid value'}, status=400)
                if key == 'offer_name' and not value:
                    return Response({key: 'Required'}, status=400)
                if key == 'payment_amount' and value <= 0:
                    return Response({key: 'Must be greater than zero'}, status=400)
                if key == 'bonus_percentage' and (value < 0 or value > 100):
                    return Response({key: 'Must be between 0 and 100'}, status=400)
                if key == 'duration_months' and value is None:
                    return Response({key: 'Duration must be at least 12 months.'}, status=400)
                setattr(x, field, value)
        if 'total_credit' in request.data:
            return Response({'total_credit': 'Calculated from payment amount, bonus and duration; do not set directly'}, status=400)
        if recalculate:
            try:
                x.total_credit = mc.total_credit(x.payment_amount, x.bonus_percentage, x.duration_months)
            except mc.CreditConfigError as exc:
                return Response({'detail': str(exc)}, status=400)
        if 'status' in request.data:
            if request.data['status'] not in ('ACTIVE', 'INACTIVE'):
                return Response({'status': 'Use ACTIVE or INACTIVE'}, status=400)
            x.status = request.data['status']
        if 'image_path' in request.data:
            x.image_path = request.data['image_path'] or None
        x.updated_at = timezone.now()
        x.save()
        return Response({'id': x.id, 'offer_name': x.offer_name, 'payment_amount': str(x.payment_amount), 'bonus_percentage': str(x.bonus_percentage), 'duration_months': x.duration_months, 'monthly_bonus': str(mc.monthly_credit_release(x.payment_amount, x.bonus_percentage)), 'total_credit': str(mc.total_credit(x.payment_amount, x.bonus_percentage, x.duration_months)), 'benefit': str(mc.total_credit(x.payment_amount, x.bonus_percentage, x.duration_months)), 'status': x.status})

    def delete(self, request):
        try:
            rid = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError):
            return Response({'id': 'Valid offer id required'}, status=400)
        if AdvancePayOffer.objects.filter(pk=rid).exists():
            if AdvancePayAllocation.objects.filter(offer_id=rid).exists():
                return Response({'detail': 'Offer has payment allocations; deactivate it instead'}, status=409)
            AdvancePayOffer.objects.filter(pk=rid).delete()
            return Response(status=204)
        return Response({'detail': 'Offer not found'}, status=404)

class ReportsAdminView(BaseAdminResource):
    required_resource='reports'
    def get(self,request):
        from django.db.models import Count, Sum, Case, When, Value, DecimalField
        from django.db.models.functions import Lower, Trim
        from legacydb.models import Checkout, LegacyUser, Product, Category
        from .finance import REVENUE_STATUS_KEYS
        orders=Checkout.objects.annotate(_normalized_status=Lower(Trim('status')))
        completed_revenue=Case(When(_normalized_status__in=REVENUE_STATUS_KEYS,then='total_amount'),default=Value(0),output_field=DecimalField(max_digits=10,decimal_places=2))
        by_status=list(orders.values('status').annotate(count=Count('order_id'),revenue=Sum(completed_revenue)).order_by('status'))
        recent=list(orders.order_by('-order_date').values('order_id','full_name','email','total_amount','status','order_date')[:50])
        total_revenue=orders.aggregate(total=Sum(completed_revenue))['total'] or 0
        return Response({'totals':{'customers':LegacyUser.objects.count(),'products':Product.objects.count(),'categories':Category.objects.count(),'orders':Checkout.objects.count(),'revenue':str(total_revenue)},'orders_by_status':by_status,'recent_orders':recent})




class LocationAdminView(BaseAdminResource):
    """CRUD for the existing unmanaged zg_location table; no schema changes."""
    required_resource = 'locations'

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid pagination'}, status=400)
        where = ''
        params = []
        if search:
            where = ' WHERE city_name ILIKE %s'
            params.append('%' + search + '%')
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM zg_location' + where, params)
            count = cursor.fetchone()[0]
            cursor.execute(
                'SELECT location_id, city_name FROM zg_location' + where +
                ' ORDER BY city_name, location_id LIMIT %s OFFSET %s',
                [*params, size, (page - 1) * size],
            )
            rows = [{'id': row[0], 'city_name': row[1]} for row in cursor.fetchall()]
        return Response({'count': count, 'page': page, 'page_size': size, 'results': rows})

    def post(self, request):
        city_name = str(request.data.get('city_name', '')).strip()
        if not city_name:
            return Response({'city_name': 'Required'}, status=400)
        if len(city_name) > 100:
            return Response({'city_name': 'Maximum length is 100 characters'}, status=400)
        try:
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO zg_location (city_name) VALUES (%s) RETURNING location_id', [city_name])
                location_id = cursor.fetchone()[0]
        except Exception as exc:
            log_db_error('Location create', exc)
            return Response({'city_name': 'Could not create location; the city may already exist'}, status=400)
        return Response({'id': location_id, 'city_name': city_name}, status=201)

    def patch(self, request):
        try:
            location_id = int(request.data.get('id'))
        except (ValueError, TypeError):
            return Response({'id': 'Valid location id required'}, status=400)
        city_name = str(request.data.get('city_name', '')).strip()
        if not city_name or len(city_name) > 100:
            return Response({'city_name': 'Required; maximum length is 100 characters'}, status=400)
        with connection.cursor() as cursor:
            cursor.execute('SELECT city_name FROM zg_location WHERE location_id=%s', [location_id])
            row = cursor.fetchone()
            if not row:
                return Response({'detail': 'Location not found'}, status=404)
            try:
                cursor.execute('UPDATE zg_location SET city_name=%s WHERE location_id=%s',
                               [city_name, location_id])
            except Exception:
                return Response({'city_name': 'Could not update location; the city may already exist'}, status=400)
        return Response({'id': location_id, 'city_name': city_name})

    def delete(self, request):
        try:
            location_id = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError):
            return Response({'id': 'Valid location id required'}, status=400)
        with connection.cursor() as cursor:
            cursor.execute('SELECT city_name FROM zg_location WHERE location_id=%s', [location_id])
            row = cursor.fetchone()
            if not row:
                return Response({'detail': 'Location not found'}, status=404)
            city_name = row[0]
            cursor.execute('SELECT COUNT(*) FROM users WHERE city=%s', [city_name])
            customer_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM zg_warehouse WHERE place=%s', [city_name])
            warehouse_count = cursor.fetchone()[0]
            if customer_count or warehouse_count:
                return Response({'detail': 'Location is referenced by customers or warehouses; update references first'}, status=409)
            cursor.execute('DELETE FROM zg_location WHERE location_id=%s', [location_id])
        return Response(status=204)


def parse_category_id(raw):
    """Return a positive int category id, or None. Accepts 5 or "5"; rejects names, booleans, floats, blanks."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    text = str(raw).strip()
    return int(text) if text.isascii() and text.isdigit() and int(text) > 0 else None


_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
_SAFE_RELATIVE_PATH = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_./-]*$')


def is_valid_reward_image(value):
    """Accept an uploaded/legacy relative image path or an http(s) URL; reject traversal and other schemes."""
    lowered = value.lower()
    if lowered.startswith(('http://', 'https://')):
        return ' ' not in value and len(value) > 8
    if '..' in value or '//' in value or not _SAFE_RELATIVE_PATH.match(value):
        return False
    return lowered.endswith(_IMAGE_EXTENSIONS)


def reward_image_url(path, request=None):
    if not path:
        return ''
    if path.lower().startswith(('http://', 'https://')):
        return path
    from .image_urls import image_url
    return image_url(path, request) or ''


class TargetAssignmentAdminView(BaseAdminResource):
    """Explicit, admin-only assignment of an existing target scheme to one active legacy user.

    Does not auto-assign schemes or create achievement/progress records.
    """
    required_resource = "targets"

    def get(self, request):
        qs = TargetAssignment.objects.order_by("-created_at", "-assignment_id")
        target_id = request.query_params.get("target_id")
        user_id = request.query_params.get("user_id")
        try:
            if target_id not in (None, ""): qs = qs.filter(target_id=int(target_id))
            if user_id not in (None, ""): qs = qs.filter(user_id=int(user_id))
        except (TypeError, ValueError):
            return Response({"detail": "target_id and user_id must be positive integers"}, status=400)
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
        start = (page - 1) * page_size
        rows = list(qs[start:start + page_size])
        return Response({"count": qs.count(), "page": page, "page_size": page_size, "results": [{
            "assignment_id": row.assignment_id, "target_id": row.target_id, "user_id": row.user_id,
            "achieved_amount": str(row.achieved_amount), "order_count": row.order_count,
            "status": row.status, "achieved_date": row.achieved_date.isoformat() if row.achieved_date else None,
        } for row in rows]})

    def post(self, request):
        from django.db import IntegrityError, transaction
        try:
            target_id = int(request.data.get("target_id"))
            user_id = int(request.data.get("user_id"))
            if target_id <= 0 or user_id <= 0: raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "Positive target_id and user_id are required"}, status=400)
        target = Target.objects.filter(target_id=target_id).first()
        if not target:
            return Response({"target_id": "Target scheme not found"}, status=404)
        user = LegacyUser.objects.filter(id=user_id, status="ACTIVE").first()
        if not user:
            return Response({"user_id": "Active user not found"}, status=404)
        try:
            with transaction.atomic():
                existing = TargetAssignment.objects.filter(target_id=target_id, user_id=user_id).first()
                if existing:
                    return Response({"detail": "This target is already assigned to this user", "assignment_id": existing.assignment_id, "target_id": target_id, "user_id": user_id}, status=409)
                assignment = TargetAssignment.objects.create(
                    target_id=target_id, user_id=user_id, achieved_amount=Decimal("0.00"),
                    order_count=0, status="PENDING", achieved_date=None,
                    created_at=timezone.now(), updated_at=timezone.now())
        except IntegrityError:
            existing = TargetAssignment.objects.filter(target_id=target_id, user_id=user_id).first()
            if existing:
                return Response({"detail": "This target is already assigned to this user", "assignment_id": existing.assignment_id}, status=409)
            return Response({"detail": "Could not create target assignment"}, status=400)
        return Response({"assignment_id": assignment.assignment_id, "target_id": target_id, "user_id": user_id, "status": assignment.status, "achieved_amount": str(assignment.achieved_amount), "order_count": assignment.order_count}, status=201)


class TargetAdminView(BaseAdminResource):
    """CRUD for existing zg_targets; preserves legacy enum values and assignments."""
    required_resource = 'targets'

    @staticmethod
    def serialize(row, request=None):
        return {
            'id': row.target_id, 'target_name': row.target_name, 'category_id': row.category_id,
            'target_amount': str(row.target_amount), 'reward_description': row.reward_description,
            'reward_image': row.reward_image or '', 'reward_image_url': reward_image_url(row.reward_image, request),
            'scheme_benefits': row.scheme_benefits or '',
            'start_date': row.start_date.isoformat() if row.start_date else '',
            'end_date': row.end_date.isoformat() if row.end_date else '', 'status': row.status,
        }

    def get(self, request):
        qs = Target.objects.order_by('-created_at', '-target_id')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(target_name__icontains=search) | Q(reward_description__icontains=search) |
                           Q(status__icontains=search))
        return self.page(request, qs, lambda row: self.serialize(row, request))

    def post(self, request):
        values, error = self._validated(request.data)
        if error:
            return Response(error, status=400)
        values['created_by'] = getattr(request.user, 'id', None)
        values['created_at'] = timezone.now()
        values['updated_at'] = timezone.now()
        row = Target.objects.create(**values)
        return Response(self.serialize(row, request), status=201)

    def patch(self, request):
        try:
            target_id = int(request.data.get('id'))
        except (ValueError, TypeError):
            return Response({'id': 'Valid target id required'}, status=400)
        row = Target.objects.filter(pk=target_id).first()
        if not row:
            return Response({'detail': 'Target not found'}, status=404)
        values, error = self._validated(request.data, partial=True)
        if error:
            return Response(error, status=400)
        effective_start = values.get('start_date', row.start_date)
        effective_end = values.get('end_date', row.end_date)
        if effective_start and effective_end and effective_end < effective_start:
            return Response({'end_date': 'Must be on or after start_date'}, status=400)
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = timezone.now()
        row.save()
        return Response(self.serialize(row, request))

    def delete(self, request):
        try:
            target_id = int(request.query_params.get('id', request.data.get('id')))
        except (ValueError, TypeError):
            return Response({'id': 'Valid target id required'}, status=400)
        row = Target.objects.filter(pk=target_id).first()
        if not row:
            return Response({'detail': 'Target not found'}, status=404)
        if TargetAssignment.objects.filter(target_id=target_id).exists() or TargetAchievement.objects.filter(target_id=target_id).exists():
            return Response({'detail': 'Target has assignments or achievement history; deactivate it instead'}, status=409)
        row.delete()
        return Response(status=204)

    @staticmethod
    def _validated(data, partial=False):
        from datetime import date
        fields = ('target_name', 'category_id', 'target_amount', 'reward_description',
                  'reward_image', 'scheme_benefits', 'start_date', 'end_date', 'status')
        values = {}
        for key in fields:
            if key not in data and partial:
                continue
            raw = data.get(key, '')
            if key == 'target_name':
                value = str(raw).strip()
                if not value or len(value) > 255:
                    return None, {'target_name': 'Required; maximum length is 255 characters'}
            elif key == 'category_id':
                value = parse_category_id(raw)
                if value is None:
                    return None, {'category_id': 'Valid category id required'}
                if not Category.objects.filter(pk=value).exists():
                    return None, {'category_id': 'Category not found'}
            elif key == 'target_amount':
                try:
                    value = Decimal(str(raw))
                except (InvalidOperation, ValueError, TypeError):
                    return None, {'target_amount': 'Valid amount required'}
                if not value.is_finite() or value <= 0:
                    return None, {'target_amount': 'Must be a finite amount greater than zero'}
            elif key in ('reward_description', 'reward_image', 'scheme_benefits'):
                value = str(raw).strip()
                if key == 'reward_description' and not value:
                    return None, {'reward_description': 'Required'}
                if key == 'reward_image' and len(value) > 255:
                    return None, {'reward_image': 'Maximum length is 255 characters'}
                if key == 'reward_image' and value and not is_valid_reward_image(value):
                    return None, {'reward_image': 'Upload an image (JPG, PNG, GIF or WEBP); the stored value must be an uploaded image path or an http(s) image URL'}
                if key == 'scheme_benefits' and not value:
                    value = None
                if key == 'reward_image' and not value:
                    value = None
            elif key in ('start_date', 'end_date'):
                try:
                    value = date.fromisoformat(str(raw))
                except (ValueError, TypeError):
                    return None, {key: 'Use YYYY-MM-DD'}
            else:
                value = str(raw).upper()
                if value not in ('ACTIVE', 'INACTIVE', 'COMPLETED'):
                    return None, {'status': 'Use ACTIVE, INACTIVE or COMPLETED'}
            values[key] = value
        start = values.get('start_date')
        end = values.get('end_date')
        if start and end and end < start:
            return None, {'end_date': 'Must be on or after start_date'}
        return values, None

