"""Contexto del dashboard meteorológico (043)."""

from __future__ import annotations

import json

from django.utils import timezone

from apps.meteo.models import Forecasts, Warning

VALID_RANGES = ('7d', '30d', '3m')
DEFAULT_RANGE = '7d'


def has_meteo_dashboard_access(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.groups.filter(name='Clientes').exists() and not user.is_superuser:
        return False
    return bool(
        user.is_superuser
        or user.has_perm('meteo.view_forecast')
        or user.has_perm('meteo.view_warning')
    )


def normalize_meteo_range(value) -> str:
    if value in VALID_RANGES:
        return value
    return DEFAULT_RANGE


def _range_start(selected_range):
    days = 30 if selected_range == '30d' else 90 if selected_range == '3m' else 7
    return timezone.localdate() - timezone.timedelta(days=days)


def _region_temp(f, region_key, period):
    data = getattr(f, region_key)
    return (
        float(data[period]['temp'])
        if data and data.get(period) and data[period].get('temp')
        else 0.0
    )


def build_forecast_series(start_date):
    forecasts = Forecasts.objects.filter(date__gte=start_date).order_by('date')
    total_forecasts = forecasts.count()
    if total_forecasts > 30:
        step = total_forecasts // 30
        forecast_ids = forecasts.values_list('id', flat=True)
        sampled_ids = forecast_ids[::step]
        forecasts = Forecasts.objects.filter(id__in=sampled_ids).order_by('date')
    has_forecasts = forecasts.exists()
    if not has_forecasts:
        return {'has_forecasts': False}
    forecasts_list = list(forecasts)
    return {
        'has_forecasts': True,
        'temperature_labels': json.dumps([f.date.strftime('%d/%m') for f in forecasts_list]),
        'max_temperatures_north': json.dumps(
            [_region_temp(f, 'north', 'afternoon') for f in forecasts_list]
        ),
        'min_temperatures_north': json.dumps(
            [_region_temp(f, 'north', 'night') for f in forecasts_list]
        ),
        'max_temperatures_south': json.dumps(
            [_region_temp(f, 'south', 'afternoon') for f in forecasts_list]
        ),
        'min_temperatures_south': json.dumps(
            [_region_temp(f, 'south', 'night') for f in forecasts_list]
        ),
        'max_temperatures_inland': json.dumps(
            [_region_temp(f, 'interior', 'afternoon') for f in forecasts_list]
        ),
        'min_temperatures_inland': json.dumps(
            [_region_temp(f, 'interior', 'night') for f in forecasts_list]
        ),
    }


def build_alerts_block(now=None):
    now = now or timezone.now()
    latest_early = (
        Warning.objects.filter(warning_type='early', valid_until__gte=now).order_by('-date').first()
    )
    latest_cyclone = (
        Warning.objects.filter(warning_type='tropical_cyclone', valid_until__gte=now)
        .order_by('-date')
        .first()
    )
    latest_storm = (
        Warning.objects.filter(warning_type='storm', valid_until__gte=now).order_by('-date').first()
    )
    return {
        'early_warnings': [latest_early] if latest_early else [],
        'tropical_cyclones': [latest_cyclone] if latest_cyclone else [],
        'storm_warnings': [latest_storm] if latest_storm else [],
    }


def get_meteo_dashboard_context(*, range=DEFAULT_RANGE, now=None):
    now = now or timezone.now()
    selected_range = normalize_meteo_range(range)
    latest_forecast = (
        Forecasts.objects.prefetch_related('regions', 'extended_days').order_by('-date').first()
    )
    forecast_series = build_forecast_series(_range_start(selected_range))
    alerts = build_alerts_block(now=now)
    active_alerts_count = sum(len(v) for v in alerts.values())
    today = timezone.localdate()
    forecast_age_days = (today - latest_forecast.date).days if latest_forecast else None
    forecast_is_current = latest_forecast is not None and forecast_age_days == 0
    return {
        'selected_range': selected_range,
        'latest_forecast': latest_forecast,
        'latest_alerts': alerts,
        'active_alerts_count': active_alerts_count,
        'forecast_age_days': forecast_age_days,
        'forecast_is_current': forecast_is_current,
        'early_count': len(alerts['early_warnings']),
        'cyclone_count': len(alerts['tropical_cyclones']),
        'storm_count': len(alerts['storm_warnings']),
        **forecast_series,
    }
