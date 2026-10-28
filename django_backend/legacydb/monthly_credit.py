"""Single source of truth for StokIt monthly credit ("Credit Release") rules.

Every credit surface (admin allocation table, admin order confirmation, customer ``crd_rel``,
customer cart, order detail) must use this module so they can never disagree.

Business rules implemented here
-------------------------------
* ``monthly_credit_release = payment_amount x bonus_percentage / 100`` (Decimal, 2 dp, half-up).
* ``total_credit = monthly_credit_release x duration_months``. The ``total_credit`` column stored on
  allocations/offers is NOT trusted for spending decisions (some stored values predate this formula).
* Remaining credit for the current calendar month (the "release period"):
  ``carried_forward = max(0, monthly_credit_release x eligible months before this one - valid CREDIT_USED before this month)``
  ``available_credit = monthly_credit_release (this month) + carried_forward``
  ``remaining_this_month = max(0, available_credit - valid CREDIT_USED in this month)``.
  Unused credit therefore carries forward month after month, but only as its *unused remainder* (a prior month's
  original allocation is never re-added, a purchase is deducted once, and the balance is never negative).
  A purchase larger than the remaining credit is covered only up to the remaining credit (``credit_to_apply``);
  the excess is paid by the customer. Nothing is borrowed from later months. Carried credit is usable only while the
  allocation is active and inside its duration: when the allocation ends or expires any unused balance lapses.
* Eligible months: calendar month index ``k = months between the start month and today`` must satisfy
  ``0 <= k < duration_months`` and ``start_date <= today <= end_date``. The start month counts as a full
  month (no proration), matching the pre-existing behaviour. Outside that window the allowance is zero.
* Customers with no ACTIVE allocation get zero credit. There is no global/default fallback.
* Valid usage = ``CREDIT_USED`` ledger rows except manual balance adjustments
  (``reference_type = 'MANUAL_ADJUSTMENT'``). Manual ``CREDIT_ADDED`` rows never raise the allowance.
  Historical ``MONTHLY_RELEASE:`` markers are preserved as audit records but are not needed: the allowance
  is derived from the offer terms, so repeated requests cannot release extra credit.
* ``advance_pay_allocations.used_credit`` / ``remaining_credit`` keep their PHP-compatible LIFETIME meaning
  (used += applied, remaining decremented and floored at zero). They are never used to decide eligibility.

Time handling: ``USE_TZ`` is False, so the database stores naive timestamps. "Now" is therefore taken from
``settings.TIME_ZONE`` explicitly (never from the OS clock, which differs on some hosts), and every ledger
write passes an explicit naive timestamp in that same zone.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from django.utils import timezone as dj_timezone

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
USAGE_TYPE = "CREDIT_USED"
ORDER_REFERENCE_TYPE = "ORDER_BONUS"
MANUAL_ADJUSTMENT_REFERENCE_TYPE = "MANUAL_ADJUSTMENT"


class CreditError(ValueError):
    """Base class for credit rule violations."""


class CreditConfigError(CreditError):
    """An allocation/offer value is missing, negative, non-finite or malformed."""


class CreditLimitError(CreditError):
    """A purchase or deduction is negative, non-finite or exceeds the allowed credit."""


# --------------------------------------------------------------------------- time
def local_now():
    """Naive datetime in the configured application time zone (settings.TIME_ZONE)."""
    return datetime.now(dj_timezone.get_default_timezone()).replace(tzinfo=None)


def local_today():
    return local_now().date()


def month_first(day):
    return day.replace(day=1)


def month_next_first(day):
    return date(day.year + (day.month == 12), 1 if day.month == 12 else day.month + 1, 1)


def month_last(day):
    return month_next_first(day) - timedelta(days=1)


def month_bounds(day):
    """Naive [start, next_start) datetimes for the calendar month containing ``day``."""
    return datetime.combine(month_first(day), time.min), datetime.combine(month_next_first(day), time.min)


def month_index(start_date, day):
    """0 for the allocation's start month, 1 for the next calendar month, negative before it."""
    return (day.year - start_date.year) * 12 + day.month - start_date.month


# ------------------------------------------------------------------------ decimals
def money(value):
    """Lenient 2dp Decimal for ledger/database values (None -> 0). Non-finite values raise."""
    if value is None:
        return ZERO
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise CreditConfigError("Amount is not a number")
    if not number.is_finite():
        raise CreditConfigError("Amount must be finite")
    return number.quantize(CENT, rounding=ROUND_HALF_UP)


def _strict(value, name):
    if value is None or isinstance(value, bool):
        raise CreditConfigError("%s is missing" % name)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise CreditConfigError("%s is not a number" % name)
    if not number.is_finite():
        raise CreditConfigError("%s must be finite" % name)
    if number < 0:
        raise CreditConfigError("%s must not be negative" % name)
    return number


def _months(value):
    if value is None or isinstance(value, bool):
        raise CreditConfigError("duration_months is missing")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise CreditConfigError("duration_months is not a number")
    if not number.is_finite() or number != number.to_integral_value() or number < 1:
        raise CreditConfigError("duration_months must be a whole number of at least 1")
    return int(number)


def monthly_credit_release(payment_amount, bonus_percentage):
    """payment_amount x bonus_percentage / 100, rounded half-up to 2 dp."""
    payment = _strict(payment_amount, "payment_amount")
    bonus = _strict(bonus_percentage, "bonus_percentage")
    return (payment * bonus / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)


def total_credit(payment_amount, bonus_percentage, duration_months):
    """monthly_credit_release x duration_months."""
    monthly = monthly_credit_release(payment_amount, bonus_percentage)
    return (monthly * _months(duration_months)).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_purchase(amount, name="purchase amount"):
    """Validate a purchase/deduction amount: finite and not negative."""
    if amount is None or isinstance(amount, bool):
        raise CreditLimitError("%s is missing" % name)
    try:
        number = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise CreditLimitError("%s is not a number" % name)
    if not number.is_finite():
        raise CreditLimitError("%s must be finite" % name)
    if number < 0:
        raise CreditLimitError("%s must not be negative" % name)
    return number.quantize(CENT, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- state evaluation
@dataclass(frozen=True)
class AllocationTerms:
    allocation_id: int
    user_id: int
    payment_amount: object
    bonus_percentage: object
    duration_months: object
    start_date: date
    end_date: date
    status: str


@dataclass(frozen=True)
class CreditState:
    allocation_id: Optional[int]
    code: str  # active | no_allocation | not_started | expired | inactive | invalid
    message: str
    eligible: bool
    payment_amount: Decimal
    bonus_percentage: Decimal
    duration_months: int
    monthly_credit_release: Decimal
    total_credit: Decimal
    month: str
    used_this_month: Decimal
    remaining_this_month: Decimal
    lifetime_used: Decimal
    start_date: Optional[date]
    end_date: Optional[date]
    allocation_status: str
    carried_forward: Decimal = ZERO  # unused balance of earlier months usable this month
    available_credit: Decimal = ZERO  # this month's allocation + carried_forward (before this month's usage)

    def as_dict(self):
        return {
            "allocation_id": self.allocation_id, "credit_status": self.code, "message": self.message,
            "payment_amount": self.payment_amount, "bonus_percentage": self.bonus_percentage,
            "duration_months": self.duration_months, "monthly_credit_release": self.monthly_credit_release,
            "total_credit": self.total_credit, "month": self.month, "monthly_used_credit": self.used_this_month,
            "monthly_remaining_credit": self.remaining_this_month, "lifetime_used_credit": self.lifetime_used,
            "allocation_start_date": self.start_date, "allocation_end_date": self.end_date,
            "allocation_status": self.allocation_status,
            "carried_forward_credit": self.carried_forward, "available_credit": self.available_credit,
            "used_credit": self.used_this_month, "remaining_credit": self.remaining_this_month,
        }


def no_allocation_state(today):
    return CreditState(None, "no_allocation", "No active credit allocation.", False, ZERO, ZERO, 0, ZERO, ZERO,
                       today.strftime("%Y-%m"), ZERO, ZERO, ZERO, None, None, "")


def spend_status(terms, today):
    """Return (code, message) describing whether ``today`` may spend credit under ``terms``."""
    if str(terms.status or "").upper() != "ACTIVE":
        return "inactive", "Allocation is not active."
    if today < terms.start_date:
        return "not_started", "Allocation has not started."
    if today > terms.end_date:
        return "expired", "Allocation has expired."
    index = month_index(terms.start_date, today)
    if index < 0:
        return "not_started", "Allocation has not started."
    if index >= _months(terms.duration_months):
        return "expired", "The offer duration has ended."
    return "active", "Monthly credit available."


def is_month_eligible(terms, day):
    """True if the calendar month containing ``day`` is inside the offer duration and date range."""
    try:
        duration = _months(terms.duration_months)
    except CreditConfigError:
        return False
    index = month_index(terms.start_date, day)
    if index < 0 or index >= duration:
        return False
    return month_first(day) <= terms.end_date and month_last(day) >= terms.start_date


def month_allowance(terms, day):
    """Monthly credit release for the month containing ``day``; zero if that month is not eligible."""
    if not is_month_eligible(terms, day):
        return ZERO
    return monthly_credit_release(terms.payment_amount, terms.bonus_percentage)


def months_released_to_date(terms, today):
    """Number of eligible months whose allowance has been released up to ``today`` (used or expired)."""
    try:
        duration = _months(terms.duration_months)
    except CreditConfigError:
        return 0
    cap_day = min(today, terms.end_date)
    if cap_day < terms.start_date:
        return 0
    return max(0, min(duration, month_index(terms.start_date, cap_day) + 1))


def carry_forward_into(terms, day, used_before_month):
    """Unused credit carried into the month containing ``day`` (pure).

    = max(0, monthly allowance x eligible months before that month - valid usage before that month). Only the
    unused remainder of earlier months is carried, so no allocation is counted twice. Zero when ``day`` is outside
    the offer window or the terms are invalid.
    """
    if not is_month_eligible(terms, day):
        return ZERO
    try:
        monthly = monthly_credit_release(terms.payment_amount, terms.bonus_percentage)
        prior_months = min(_months(terms.duration_months), month_index(terms.start_date, day))
    except CreditConfigError:
        return ZERO
    if prior_months <= 0:
        return ZERO
    return max(ZERO, monthly * prior_months - money(used_before_month)).quantize(CENT, rounding=ROUND_HALF_UP)


def evaluate(terms, used_this_month, lifetime_used, today):
    """Compute the full credit state for one allocation on ``today`` (pure; no database access)."""
    month = today.strftime("%Y-%m")
    used = money(used_this_month)
    lifetime = money(lifetime_used)
    try:
        monthly = monthly_credit_release(terms.payment_amount, terms.bonus_percentage)
        total = total_credit(terms.payment_amount, terms.bonus_percentage, terms.duration_months)
        payment = _strict(terms.payment_amount, "payment_amount").quantize(CENT)
        bonus = _strict(terms.bonus_percentage, "bonus_percentage").quantize(CENT)
        duration = _months(terms.duration_months)
    except CreditConfigError as exc:
        return CreditState(terms.allocation_id, "invalid", str(exc), False, ZERO, ZERO, 0, ZERO, ZERO, month,
                           used, ZERO, lifetime, terms.start_date, terms.end_date, str(terms.status or ""))
    code, message = spend_status(terms, today)
    eligible = code == "active"
    # Usage before this month = lifetime usage minus this month's usage (never negative).
    carried = carry_forward_into(terms, today, max(ZERO, lifetime - used)) if eligible else ZERO
    available = (monthly + carried) if eligible else ZERO
    remaining = max(ZERO, available - used) if eligible else ZERO
    return CreditState(terms.allocation_id, code, message, eligible, payment, bonus, duration, monthly, total,
                       month, used, remaining, lifetime, terms.start_date, terms.end_date, str(terms.status or ""),
                       carried, available)


def credit_to_apply(state, purchase_amount):
    """Credit applied to a purchase: min(this month's remaining credit, purchase). Rejects negatives."""
    purchase = parse_purchase(purchase_amount)
    return min(state.remaining_this_month, purchase)


def is_valid_usage(transaction_type, reference_type):
    return str(transaction_type or "").upper() == USAGE_TYPE and str(reference_type or "") != MANUAL_ADJUSTMENT_REFERENCE_TYPE


def sum_valid_usage(transactions, start=None, end=None):
    """Sum valid CREDIT_USED amounts from objects exposing transaction_type/amount/reference_type/created_at."""
    total = ZERO
    for tx in transactions:
        if not is_valid_usage(getattr(tx, "transaction_type", None), getattr(tx, "reference_type", None)):
            continue
        created = getattr(tx, "created_at", None)
        if start is not None or end is not None:
            if created is None:
                continue
            if getattr(created, "tzinfo", None) is not None:
                created = created.astimezone(dj_timezone.get_default_timezone()).replace(tzinfo=None)
            if (start is not None and created < start) or (end is not None and created >= end):
                continue
        total += money(tx.amount)
    return total


# --------------------------------------------------------------------- database
_ALLOCATION_COLUMNS = "id, user_id, payment_amount, bonus_percentage, duration_months, start_date, end_date, status"


def user_id_for_email(cursor, email, lock=False):
    cursor.execute("SELECT id FROM users WHERE email=%s ORDER BY id LIMIT 1" + (" FOR UPDATE" if lock else ""), [email])
    row = cursor.fetchone()
    return row[0] if row else None


def select_allocation(cursor, user_id, today, lock=False):
    """The customer's ACTIVE allocation, preferring one whose date range contains ``today`` (then highest id)."""
    cursor.execute(
        "SELECT " + _ALLOCATION_COLUMNS + " FROM advance_pay_allocations WHERE user_id=%s AND UPPER(status)='ACTIVE' "
        "ORDER BY (start_date <= %s AND end_date >= %s) DESC, id DESC LIMIT 1" + (" FOR UPDATE" if lock else ""),
        [user_id, today, today],
    )
    row = cursor.fetchone()
    return AllocationTerms(*row) if row else None


def usage_in_month(cursor, allocation_id, day):
    start, end = month_bounds(day)
    cursor.execute(
        "SELECT COALESCE(SUM(amount),0) FROM advance_pay_transactions WHERE allocation_id=%s "
        "AND UPPER(transaction_type)='CREDIT_USED' AND COALESCE(reference_type,'') <> %s "
        "AND created_at >= %s AND created_at < %s",
        [allocation_id, MANUAL_ADJUSTMENT_REFERENCE_TYPE, start, end],
    )
    return money(cursor.fetchone()[0])


def lifetime_usage(cursor, allocation_id):
    cursor.execute(
        "SELECT COALESCE(SUM(amount),0) FROM advance_pay_transactions WHERE allocation_id=%s "
        "AND UPPER(transaction_type)='CREDIT_USED' AND COALESCE(reference_type,'') <> %s",
        [allocation_id, MANUAL_ADJUSTMENT_REFERENCE_TYPE],
    )
    return money(cursor.fetchone()[0])


def load_state(cursor, user_id, today=None, lock=False):
    """Return (state, terms). ``lock=True`` row-locks the allocation (call inside a transaction)."""
    today = today or local_today()
    terms = select_allocation(cursor, user_id, today, lock=lock)
    if terms is None:
        return no_allocation_state(today), None
    return evaluate(terms, usage_in_month(cursor, terms.allocation_id, today), lifetime_usage(cursor, terms.allocation_id), today), terms


def order_credit_applied(cursor, allocation_id):
    """{order_id: (amount, created_at)} for committed order deductions of an allocation."""
    cursor.execute(
        "SELECT reference_id, SUM(amount), MIN(created_at) FROM advance_pay_transactions WHERE allocation_id=%s "
        "AND reference_type=%s AND UPPER(transaction_type)='CREDIT_USED' AND reference_id IS NOT NULL GROUP BY reference_id",
        [allocation_id, ORDER_REFERENCE_TYPE],
    )
    return {int(r[0]): (money(r[1]), r[2]) for r in cursor.fetchall()}


def customer_credit_context(cursor, email=None, today=None, user_id=None):
    """Everything customer-facing endpoints need, read-only. Prefer authenticated users.id over email matching."""
    today = today or local_today()
    if user_id is None:
        user_id = user_id_for_email(cursor, email) if email else None
    if user_id is None:
        return {"state": no_allocation_state(today), "terms": None, "applied": {}, "today": today}
    state, terms = load_state(cursor, user_id, today)
    applied = order_credit_applied(cursor, terms.allocation_id) if terms else {}
    return {"state": state, "terms": terms, "applied": applied, "today": today}


def commit_order_credit(cursor, order_id, user_id, purchase_amount, now=None, allow_new=True, record_zero=False):
    """Atomically apply this month's credit to an order. The caller MUST already be inside a transaction.

    1. Locks the allocation row (blocks concurrent deductions for the same customer).
    2. Recomputes the current month from now (configured time zone) and reads valid usage.
    3. Returns the recorded deduction unchanged if this order was already processed (idempotent).
    4. Inserts one CREDIT_USED/ORDER_BONUS ledger row and updates the lifetime summary columns by delta.
       With allow_new=False (a repeat confirmation of an order that was already confirmed once) no new
       deduction is ever created, so an order that got zero credit the first time cannot be charged later.
       With record_zero=True (order placement) an order that receives no credit still gets a zero-amount ledger
       row, so the order is marked as processed: a later admin confirmation (possibly in another month) finds it
       and can never deduct credit for it. Zero rows do not change any balance.
    Returns ``None`` when the customer has no ACTIVE allocation (nothing is recorded then).
    """
    now = now or local_now()
    today = now.date()
    purchase = parse_purchase(purchase_amount)
    # Serialize purchases by canonical customer before reading the ledger. The placement view also locks this row,
    # but the service-level lock protects admin confirmation and any other caller.
    cursor.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", [int(user_id)])
    if not cursor.fetchone():
        raise CreditError("Authenticated customer no longer exists; credit was not applied.")
    state, terms = load_state(cursor, int(user_id), today, lock=True)
    if terms is None:
        return None
    cursor.execute(
        # Order ids are unique, so the lookup is deliberately NOT limited to the current allocation: an order that was
        # deducted at placement stays deducted even if the customer's active allocation changed before confirmation.
        "SELECT amount FROM advance_pay_transactions WHERE reference_type=%s AND reference_id=%s "
        "AND UPPER(transaction_type)='CREDIT_USED' LIMIT 1",
        [ORDER_REFERENCE_TYPE, order_id],
    )
    existing = cursor.fetchone()
    if existing:
        applied = money(existing[0])
        return result_dict(state, purchase, applied, duplicate=True, remaining_after=state.remaining_this_month)
    if not allow_new:
        return result_dict(state, purchase, ZERO, duplicate=True, remaining_after=state.remaining_this_month)
    applied = credit_to_apply(state, purchase)
    if applied > ZERO or record_zero:
        note = ("Monthly credit applied to order #%s (%s)" if applied > ZERO
                else "No monthly credit available for order #%s (%s)") % (order_id, now.strftime("%Y-%m"))
        cursor.execute(
            "INSERT INTO advance_pay_transactions (allocation_id,user_id,amount,transaction_type,reference_id,reference_type,notes,created_at) "
            "VALUES (%s,%s,%s,'CREDIT_USED',%s,%s,%s,%s)",
            [terms.allocation_id, user_id, applied, order_id, ORDER_REFERENCE_TYPE, note, now],
        )
    if applied > ZERO:
        cursor.execute(
            "UPDATE advance_pay_allocations SET used_credit=COALESCE(used_credit,0)+%s, "
            "remaining_credit=GREATEST(0, COALESCE(remaining_credit,0)-%s), updated_at=%s WHERE id=%s",
            [applied, applied, now, terms.allocation_id],
        )
    return result_dict(state, purchase, applied, duplicate=False, remaining_after=max(ZERO, state.remaining_this_month - applied))


def result_dict(state, purchase, applied, duplicate, remaining_after):
    """Admin-facing result; keeps the legacy key names. ``carried_forward`` is the unused balance of earlier months."""
    data = state.as_dict()
    data.update({
        "offer_payment_amount": state.payment_amount, "monthly_bonus": state.monthly_credit_release,
        "carried_forward": state.carried_forward, "available_bonus": state.remaining_this_month, "purchase_amount": purchase,
        "bonus_applied": applied, "amount_payable": max(ZERO, purchase - applied), "remaining_bonus": remaining_after,
        "duplicate": duplicate, "monthly_released_now": ZERO,
    })
    if duplicate:
        data["credit_status"] = "already_applied"
    elif state.eligible:
        data["credit_status"] = "applied" if applied > ZERO else "no_bonus_applied"
    return data
