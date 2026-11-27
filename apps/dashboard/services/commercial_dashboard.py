"""Contexto del dashboard comercial (042).

Centraliza la lógica comercial para que la vista y el dashboard legacy no la
dupliquen. Las consultas filtran `record_active=True` donde corresponde.
"""

from __future__ import annotations

import json

from django.db.models import Exists, OuterRef, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.commercial.models import Invoice, InvoiceItem, ServiceSubscription

VALID_INCOME_RANGES = ('1m', '3m', '6m', '12m', 'all')
DEFAULT_INCOME_RANGE = '12m'
DRILLDOWN_LIMIT = 20


paid_direct = Exists(
    ServiceSubscription.objects.filter(
        id=OuterRef('subscription_id'), payment_status='paid', record_active=True
    )
)

paid_via_items = Exists(
    InvoiceItem.objects.filter(
        invoice_id=OuterRef('id'),
        subscription__payment_status='paid',
        subscription__record_active=True,
    )
)


def has_commercial_dashboard_access(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.groups.filter(name='Clientes').exists() and not user.is_superuser:
        return False
    return bool(
        user.is_superuser
        or user.has_perm('commercial.view_subscription')
        or user.has_perm('commercial.view_invoice')
    )


def normalize_income_range(value) -> str:
    if value in VALID_INCOME_RANGES:
        return value
    return DEFAULT_INCOME_RANGE


def _income_num_months(income_range, now):
    if income_range == '1m':
        return 1
    if income_range == '3m':
        return 3
    if income_range == '6m':
        return 6
    if income_range == 'all':
        earliest = Invoice.objects.filter(is_cancelled=False).order_by('issue_date').first()
        if earliest and earliest.issue_date:
            return max((now - earliest.issue_date).days // 30, 1)
        return 12
    return 12


def _month_floor(now):
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def build_commercial_income(income_range, *, now=None):
    now = now or timezone.now()
    income_range = normalize_income_range(income_range)
    month_start = _month_floor(now)
    num_months = _income_num_months(income_range, now)
    income_start = month_start - timezone.timedelta(days=num_months * 30)

    billed_qs = (
        Invoice.objects.filter(is_cancelled=False, issue_date__gte=income_start)
        .values('issue_date__year', 'issue_date__month')
        .annotate(total=Sum('amount'))
        .order_by('issue_date__year', 'issue_date__month')
    )
    paid_qs = (
        Invoice.objects.filter(is_cancelled=False, issue_date__gte=income_start)
        .filter(paid_direct | paid_via_items)
        .values('issue_date__year', 'issue_date__month')
        .annotate(total=Sum('amount'))
        .order_by('issue_date__year', 'issue_date__month')
    )

    billed_map = {
        (entry['issue_date__year'], entry['issue_date__month']): float(entry['total'])
        for entry in billed_qs
    }
    paid_map = {
        (entry['issue_date__year'], entry['issue_date__month']): float(entry['total'])
        for entry in paid_qs
    }

    months_labels = []
    billed_data = []
    paid_data = []
    for i in range(num_months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        months_labels.append(f'{m:02d}/{y}')
        billed_data.append(billed_map.get((y, m), 0))
        paid_data.append(paid_map.get((y, m), 0))

    return {
        'income_months': json.dumps(months_labels),
        'income_billed_data': json.dumps(billed_data),
        'income_paid_data': json.dumps(paid_data),
    }


def serialize_sub(sub):
    import html

    return {
        'customer': html.escape(sub.customer.display_name) if sub.customer else 'N/A',
        'service': html.escape(sub.service.title or 'N/A') if sub.service else 'N/A',
        'start_date': sub.start_date.strftime('%d/%m/%Y') if sub.start_date else 'N/A',
    }


def _subscription_ordering():
    return Coalesce(
        'customer__company_name',
        'customer__user__last_name',
        'customer__user__first_name',
        'customer__user__username',
    )


def _subscription_lists(status, *, limit=DRILLDOWN_LIMIT):
    return (
        ServiceSubscription.objects.filter(payment_status=status, record_active=True)
        .select_related('customer', 'service')
        .order_by(_subscription_ordering())[:limit]
    )


def get_commercial_dashboard_context(user, *, income_range=DEFAULT_INCOME_RANGE, now=None) -> dict:
    now = now or timezone.now()
    income_range = normalize_income_range(income_range)
    month_start = _month_floor(now)
    month_end = (month_start + timezone.timedelta(days=32)).replace(day=1)

    month_income_paid = (
        Invoice.objects.filter(
            is_cancelled=False, issue_date__gte=month_start, issue_date__lt=month_end
        )
        .filter(paid_direct | paid_via_items)
        .aggregate(total=Sum('amount'))['total']
        or 0
    )

    income = build_commercial_income(income_range, now=now)

    active_qs = _subscription_lists('paid')
    pending_qs = _subscription_lists('pending')
    requested_qs = _subscription_lists('requested')

    return {
        'income_range': income_range,
        'month_income': float(month_income_paid),
        **income,
        'active_subs': ServiceSubscription.objects.filter(
            payment_status='paid', record_active=True
        ).count(),
        'pending_subs': ServiceSubscription.objects.filter(
            payment_status='pending', record_active=True
        ).count(),
        'requested_subs': ServiceSubscription.objects.filter(
            payment_status='requested', record_active=True
        ).count(),
        'active_subs_list': json.dumps([serialize_sub(s) for s in active_qs]),
        'pending_subs_list': json.dumps([serialize_sub(s) for s in pending_qs]),
        'requested_subs_list': json.dumps([serialize_sub(s) for s in requested_qs]),
    }
