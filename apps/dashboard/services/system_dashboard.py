"""Contexto del dashboard de sistema (044)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.core.models import SiteConfiguration, TaskExecutionLog
from apps.core.utils import local_day_window
from apps.dashboard.services import backup as backup_service

logger = logging.getLogger(__name__)

STALE_TASK_MINUTES = 5


def has_system_dashboard_access(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.groups.filter(name='Clientes').exists() and not user.is_superuser:
        return False
    return bool(user.is_superuser or user.has_perm('core.view_activitylog'))


def _safe_backup_status():
    try:
        status = backup_service.backup_status(settings.DB_BACKUP_STATUS_FILE)
    except Exception:
        logger.exception('No se pudo leer el estado de respaldo')
        return None
    return status


def _safe_backup_manifest():
    try:
        return backup_service.backup_manifest(settings.DB_BACKUP_MANIFEST_FILE)
    except Exception:
        logger.exception('No se pudo leer el manifiesto de respaldos')
        return {}


def get_system_dashboard_context(user=None):
    now = timezone.now()
    config = SiteConfiguration.objects.first()
    maintenance_mode = bool(config and config.maintenance_mode)

    stale_threshold = now - timezone.timedelta(minutes=STALE_TASK_MINUTES)
    task_qs = TaskExecutionLog.objects.all()
    task_stats = {
        'error': task_qs.filter(status=TaskExecutionLog.STATUS_ERROR).count(),
        'stale': task_qs.filter(
            status=TaskExecutionLog.STATUS_ENQUEUED, enqueued_at__lt=stale_threshold
        ).count(),
        'executing': task_qs.filter(status=TaskExecutionLog.STATUS_EXECUTING).count(),
        'enqueued': task_qs.filter(status=TaskExecutionLog.STATUS_ENQUEUED).count(),
        'recent': list(task_qs.order_by('-enqueued_at')[:5]),
    }
    task_stats['attention'] = task_stats['error'] + task_stats['stale']

    backup_status = _safe_backup_status()
    backup_manifest = _safe_backup_manifest() or {}
    last_backup = None
    backups = backup_manifest.get('backups') or []
    if backups:
        last_backup = backups[0]
    backup_info = {
        'status': backup_status,
        'last_backup': last_backup,
        'count': len(backups),
        'busy': bool(backup_service.is_busy(backup_status)) if backup_status else False,
        'last_state': (backup_status or {}).get('state'),
    }

    inicio_hoy, fin_hoy = local_day_window(timezone.localdate())
    user_stats = {
        'total_users': User.objects.count(),
        'active_today': User.objects.filter(
            last_login__gte=inicio_hoy, last_login__lt=fin_hoy
        ).count(),
        'staff_users': User.objects.filter(is_staff=True).count(),
        'active_sessions': Session.objects.filter(expire_date__gt=now).count(),
        'groups': Group.objects.count(),
    }

    attention_items = []
    if maintenance_mode:
        attention_items.append('Mantenimiento activo')
    if task_stats['error']:
        attention_items.append(f'{task_stats["error"]} tarea(s) con error')
    if task_stats['stale']:
        attention_items.append(f'{task_stats["stale"]} tarea(s) estancada(s)')
    if backup_info['last_state'] in {'failed', 'error'}:
        attention_items.append('Último respaldo con error')

    return {
        'maintenance_mode': maintenance_mode,
        'task_stats': task_stats,
        'backup_info': backup_info,
        'user_stats': user_stats,
        'attention_items': attention_items,
    }
