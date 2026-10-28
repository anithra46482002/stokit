import html
import json
import secrets
import uuid
from django.db import IntegrityError, transaction
from django.utils import timezone
from accounts.models import CheckoutPayload
from .common import fetchall, fetchone, jr, legacy_view, legacy_image_url

@legacy_view()
def save_check(request):
    """Persist the legacy saveCheck payload in a managed table; do not write public files."""
    if request.method != 'POST':
        return jr({'detail': 'Method not allowed'}, 405)
    try:
        raw = request.body.decode('utf-8')
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jr({'success': False, 'message': 'Invalid JSON'})
    # PHP's `if (!$decoded)` rejects null, false, zero, empty arrays and empty objects.
    if decoded is None or decoded is False or decoded == 0 or decoded == '0' or decoded == '' or decoded == [] or decoded == {}:
        return jr({'success': False, 'message': 'Invalid JSON'})
    # Preserve the old misspelled response key and a ck/checkout_*.txt-shaped reference.
    file_ref = f"ck/checkout_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.txt"
    for _ in range(3):
        legacy_id = secrets.randbelow(2_000_000_000) + 1
        try:
            with transaction.atomic():
                CheckoutPayload.objects.create(user_id=request.legacy_user['id'], payload=decoded,
                                               legacy_order_id=legacy_id)
            break
        except IntegrityError:
            continue
    else:
        return jr({'success': False, 'message': 'Could not save checkout data'}, 500)
    return jr({'success': True, 'message': 'Data saved successfully', 'file': file_ref, 'oder_id': legacy_id})

@legacy_view()
def targets(request):
    """Return target/scheme progress for the authenticated customer; never creates schema."""
    if request.method not in ('GET', 'POST', 'OPTIONS'):
        return jr({'detail': 'Method not allowed'}, 405)
    user = fetchone("SELECT id, username, fullname, email FROM users WHERE username=%s AND status='ACTIVE' LIMIT 1",
                    [request.legacy_user['username']])
    if not user:
        return jr({'success': False, 'message': 'User not found or inactive', 'targets': []})
    rows = fetchall("""
        SELECT t.target_id AS id, t.target_name AS scheme_name,
               t.reward_description AS scheme_description, t.target_amount, t.reward_image,
               t.scheme_benefits, t.start_date, t.end_date, t.status AS target_status,
               ta.achieved_amount, ta.order_count, ta.status AS assignment_status, ta.achieved_date,
               ach.total_spent, ach.order_count AS ach_order_count, ach.progress_percentage,
               ach.is_achieved, ach.last_order_date, ach.last_order_id, c.category_name
        FROM zg_target_assignments ta
        JOIN zg_targets t ON ta.target_id=t.target_id
        LEFT JOIN zg_target_achievements ach ON ta.target_id=ach.target_id AND ta.user_id=ach.user_id
        LEFT JOIN zg_category c ON t.category_id=c.category_id
        WHERE ta.user_id=%s ORDER BY t.created_at DESC
    """, [user['id']])
    targets_data, active_count = [], 0
    for row in rows:
        amount = float(row['target_amount'] or 0)
        achieved = float(row['achieved_amount'] if row['achieved_amount'] is not None else (row['total_spent'] or 0))
        progress = float(row['progress_percentage'] or 0)
        if progress == 0 and amount > 0 and achieved > 0:
            progress = min(achieved / amount * 100, 100)
        is_achieved = bool(row['is_achieved']) if row['is_achieved'] is not None else row['assignment_status'] == 'ACHIEVED'
        reward = 0
        if is_achieved:
            reward = 50 if progress >= 200 else 35 if progress >= 150 else 25 if progress >= 100 else 20
        active = row['target_status'] == 'ACTIVE' and row['assignment_status'] != 'ACHIEVED'
        if active: active_count += 1
        image = legacy_image_url(row['reward_image'], request)
        targets_data.append({
            'id': int(row['id']), 'scheme_name': html.escape(row['scheme_name'] or ''),
            'scheme_description': html.escape(row['scheme_description'] or ''), 'reward_percentage': reward,
            'image': image, 'scheme_details': html.escape(row['scheme_benefits'] or ''),
            'target_amount': amount, 'achieved_amount': achieved, 'achieved_percentage': round(progress, 2),
            'remaining_amount': round(max(0, amount-achieved), 2), 'reward_image': image,
            'scheme_benefits': html.escape(row['scheme_benefits'] or 'No benefits specified'),
            'active': 'Y' if active else 'N', 'category_name': html.escape(row['category_name'] or 'N/A'),
            'start_date': row['start_date'], 'end_date': row['end_date'],
            'order_count': int(row['order_count'] if row['order_count'] is not None else (row['ach_order_count'] or 0)),
            'is_achieved': is_achieved, 'assignment_status': row['assignment_status'],
            'achieved_date': row['achieved_date'], 'last_order_date': row['last_order_date'],
        })
    user_info = {'username': user['username'], 'email': user['email'], 'fullname': user['fullname']}
    if not targets_data:
        any_targets = fetchone('SELECT COUNT(*) AS total FROM zg_targets') or {'total': 0}
        message = 'No targets available. Please create targets first.' if int(any_targets['total']) == 0 else 'User is not assigned to any targets.'
        return jr({'success': True, 'message': message, 'targets': [], 'user_info': user_info})
    return jr({'success': True, 'user_info': user_info, 'summary': {
        'total_targets': len(targets_data), 'active_targets': active_count,
        'achieved_targets': sum(1 for item in targets_data if item['is_achieved']),
        'average_progress': round(sum(item['achieved_percentage'] for item in targets_data) / len(targets_data), 2)},
        'targets': targets_data})

@legacy_view()
def coabout(request):
    """Exact source response. URLs are PHP placeholders and intentionally not presented as real links."""
    return jr({'success': True, 'links': {
        'terms_and_conditions': 'https://www.example.com',
        'about_us': 'https://www.example.com/about',
    }})
