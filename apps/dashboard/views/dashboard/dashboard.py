import hashlib
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView, View

from apps.commercial.models import Customer, Invoice, ServiceSubscription
from apps.core.cache_utils import safe_cache_get, safe_cache_set
from apps.core.models import TaskExecutionLog
from apps.core.utils import local_day_window
from apps.dashboard.services.commercial_dashboard import (
    build_commercial_income as _build_commercial_income,
)
from apps.dashboard.services.commercial_dashboard import (
    get_commercial_dashboard_context,
    has_commercial_dashboard_access,
)
from apps.dashboard.services.commercial_dashboard import serialize_sub as serialize_sub
from apps.dashboard.services.meteo_dashboard import (
    build_alerts_block as _build_alerts_block,
)
from apps.dashboard.services.meteo_dashboard import (
    build_forecast_series as _build_forecast_series,
)
from apps.dashboard.services.meteo_dashboard import (
    has_meteo_dashboard_access,
)
from apps.dashboard.services.system_dashboard import has_system_dashboard_access
from apps.meteo.models import Forecasts

logger = logging.getLogger(__name__)


def build_shared_kpis(time_range, income_range, *, forecast=False, alerts=False, commercial=False):
    """Return user-agnostic Dashboard aggregates, cached per (range, income_range).

    Only the expensive shared aggregations are cached (forecast series, alerts,
    commercial income chart). Per-client data is NEVER placed here, so there is
    no cross-user leakage. Cached values are JSON strings / counts (picklable for
    Redis). Reads/writes use safe_cache_* so a Redis outage degrades to live compute.
    """
    cache_key = f'dashboard:kpi:{time_range}:{income_range}'
    shared = safe_cache_get(cache_key) or {}
    if forecast and 'forecast' not in shared:
        series = _build_forecast_series(
            timezone.localdate()
            - timezone.timedelta(
                days=30 if time_range == '30d' else 90 if time_range == '3m' else 7
            )
        )
        if series.get('has_forecasts'):
            shared['forecast'] = series
            safe_cache_set(cache_key, shared, 300)
    if alerts and 'alerts' not in shared:
        shared['alerts'] = _build_alerts_block()
        safe_cache_set(cache_key, shared, 300)
    if commercial and 'commercial' not in shared:
        shared['commercial'] = _build_commercial_income(income_range)
        safe_cache_set(cache_key, shared, 300)
    return shared


class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'pages/dashboard/index.html'

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_staff or user.groups.filter(name='Clientes').exists()):
            return self.handle_no_permission()
        profile_redirect = self._profile_dashboard_redirect(user, request)
        if profile_redirect:
            return profile_redirect
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _profile_dashboard_redirect(user, request):
        if user.is_superuser or user.groups.filter(name='Clientes').exists():
            return None
        commercial = has_commercial_dashboard_access(user)
        meteo = has_meteo_dashboard_access(user)
        system = has_system_dashboard_access(user)
        matches = [
            name
            for name, ok in (
                ('dashboard:commercial', commercial),
                ('dashboard:meteorologia', meteo),
                ('dashboard:sistema', system),
            )
            if ok
        ]
        if len(matches) != 1:
            return None
        url = redirect(matches[0])
        if request.META.get('QUERY_STRING'):
            url['Location'] = f'{url["Location"]}?{request.META["QUERY_STRING"]}'
        return url

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.groups.filter(name='Clientes').exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        time_range = self.request.GET.get('range', '7d')
        income_range = self.request.GET.get('income_range', '12m')

        context.update(
            {
                'title': 'Dashboard',
                'parent': '',
                'segment': 'dashboard',
                'is_superuser': user.is_superuser,
                'selected_range': time_range,
            }
        )

        context['show_alerts'] = user.has_perm('meteo.view_warning')
        context['show_forecast'] = user.has_perm('meteo.view_forecast')
        context['is_client'] = (
            user.groups.filter(name='Clientes').exists() and not user.is_superuser
        )
        context['show_commercial'] = (
            any(
                [
                    user.has_perm('commercial.view_subscription'),
                    user.has_perm('commercial.view_invoice'),
                ]
            )
            and not context['is_client']
        )

        shared = build_shared_kpis(
            time_range,
            income_range,
            forecast=context['show_forecast'],
            alerts=context['show_alerts'],
            commercial=False,
        )

        if context['is_client']:
            try:
                customer = Customer.objects.get(user=user)
                subs = ServiceSubscription.objects.filter(customer=customer, record_active=True)
                # Ninguna suscripción vence: `client_active_subs` son las pagadas
                # y no anuladas, y lo siguen siendo para siempre. Por eso no
                # existen "vencidas" ni "por vencer": una vez pagada, la única
                # forma de perder la vigencia es anularla.
                context['client_active_subs'] = subs.filter(payment_status='paid')
                context['client_pending_subs'] = subs.filter(payment_status='pending')
                context['client_requested_subs'] = subs.filter(payment_status='requested')
                context['client_invoices'] = Invoice.objects.filter(customer=customer).order_by(
                    '-issue_date'
                )[:5]
            except Customer.DoesNotExist:
                context['client_active_subs'] = ServiceSubscription.objects.none()
                context['client_pending_subs'] = ServiceSubscription.objects.none()
                context['client_requested_subs'] = ServiceSubscription.objects.none()
                context['client_invoices'] = Invoice.objects.none()

        if context['show_forecast']:
            try:
                context['latest_forecast'] = Forecasts.objects.prefetch_related(
                    'regions', 'extended_days'
                ).latest('date')
            except ObjectDoesNotExist:
                context['latest_forecast'] = None

            if 'forecast' in shared:
                context.update(shared['forecast'])

        if context['show_alerts'] and 'alerts' in shared:
            context['latest_alerts'] = shared['alerts']

        if context['show_commercial']:
            commercial = get_commercial_dashboard_context(
                self.request.user, income_range=income_range
            )
            context.update(commercial)
            context['selected_income_range'] = commercial['income_range']

        if user.is_superuser:
            inicio_hoy, fin_hoy = local_day_window(timezone.localdate())
            context['user_stats'] = {
                'total_users': User.objects.count(),
                # Rango de instantes, no `last_login__date`: el `__date` resuelve
                # America/Havana dentro de PostgreSQL con su propio tzdata y el
                # conteo se corre un dia cuando discrepa del de Python.
                'active_today': User.objects.filter(
                    last_login__gte=inicio_hoy, last_login__lt=fin_hoy
                ).count(),
                'staff_users': User.objects.filter(is_staff=True).count(),
            }

            permission_groups = (
                Group.objects.annotate(user_count=Count('user'))
                .prefetch_related('permissions', 'user_set')
                .order_by('-user_count')
            )
            paginator_groups = Paginator(permission_groups, 2)
            page_number_groups = self.request.GET.get('page_groups')
            context['permission_groups_page'] = paginator_groups.get_page(page_number_groups)

            recent_logins = User.objects.filter(
                last_login__gte=timezone.now() - timezone.timedelta(hours=24)
            ).order_by('-last_login')
            paginator_logins = Paginator(recent_logins, 2)
            page_number_logins = self.request.GET.get('page_logins')
            context['recent_logins_page'] = paginator_logins.get_page(page_number_logins)

            context['active_sessions'] = Session.objects.filter(
                expire_date__gt=timezone.now()
            ).count()

        return context


def _paso_a_reintentar(execution, paso_pedido):
    """Qué paso de la tarea de factura hay que reintentar.

    Devuelve 'pdf', 'email' o None (dejar que la tarea decida sola).

    Si el operador pidió un paso explícito, se respeta. Si no, se deduce del
    estado de la factura, que es la fuente de verdad: si el PDF quedó `ready`
    y el correo `failed`, el único paso que sirve reintentar es el correo.
    """
    if paso_pedido in ('pdf', 'email'):
        return paso_pedido
    if not (execution.logical_key or '').startswith('invoice:'):
        return None
    try:
        from apps.commercial.models import Invoice

        invoice = Invoice.objects.get(uuid=execution.logical_key.split(':', 1)[1])
    except Exception:
        return None
    if not invoice.pdf_ready and invoice.pdf_status == Invoice.PdfStatus.FAILED:
        return 'pdf'
    if invoice.email_status == Invoice.EmailStatus.FAILED:
        return 'email'
    return None


def _tabla_fingerprint(qs):
    """Token barato que cambia si y solo si cambia lo que la tabla muestra.

    El cliente lo consulta cada pocos segundos y solo descarga y repinta la
    tabla cuando el token se movió. Sin esto, estaríamos renderizando el
    partial completo cada 5 segundos para reemplazar filas idénticas, que es
    trabajo de servidor y red tirados a la basura.

    El modelo no tiene `updated_at`, así que la huella se arma con los campos
    que la tabla muestra de verdad: si ninguno cambió, la pantalla tampoco
    tiene nada nuevo que pintar.
    """
    filas = list(
        qs.values_list(
            'pk',
            'status',
            'attempts',
            'enqueued_at',
            'started_at',
            'finished_at',
            'summary',
        )
    )
    return hashlib.sha1(
        repr(filas).encode('utf-8'),
        usedforsecurity=False,
    ).hexdigest()[:16]


class TaskMonitoringView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'pages/dashboard/tasks.html'
    max_rows = 500

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, *args, **kwargs):
        # La sonda de "¿cambió algo?" no renderiza nada: responde un token.
        if request.GET.get('fingerprint'):
            return JsonResponse({'token': _tabla_fingerprint(self._queryset())})
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        # El polling del cliente pide solo la tabla (?partial=1) para
        # recargar los datos sin reconstruir la página ni la instancia de
        # DataTables: si no, cada pasada pierde el orden y la búsqueda.
        if self.request.GET.get('partial'):
            return ['pages/dashboard/tasks_table.html']
        return [self.template_name]

    def _queryset(self):
        qs = TaskExecutionLog.objects.all()
        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs[: self.max_rows]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        stale_threshold_minutes = 5

        qs = self._queryset()
        executions = qs
        stale_count = TaskExecutionLog.objects.filter(
            status=TaskExecutionLog.STATUS_ENQUEUED,
            enqueued_at__lt=now - timezone.timedelta(minutes=stale_threshold_minutes),
        ).count()
        error_count = TaskExecutionLog.objects.filter(status=TaskExecutionLog.STATUS_ERROR).count()

        context.update(
            {
                'title': 'Monitoreo de tareas',
                'parent': 'dashboard',
                'segment': 'task_monitoring',
                'executions': executions,
                'status_choices': TaskExecutionLog.STATUS_CHOICES,
                # Para marcar qué botón de filtro está aplicado: sin esto, el
                # operador no tiene forma de saber qué está viendo después de
                # filtrar, porque el filtro ya no recarga la página.
                'current_status': self.request.GET.get('status', ''),
                'stale_threshold_minutes': stale_threshold_minutes,
                'stale_count': stale_count,
                'error_count': error_count,
            }
        )
        return context


class TaskMonitoringActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Acciones POST sobre un registro de tarea: reintentar o limpiar.

    Requiere superuser (igual que la tabla). Reintentar solo es posible para
    tareas cuyos argumentos se persistieron de forma segura (RETRYABLE_TASKS).
    """

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        import json as _json
        from importlib import import_module

        from apps.core.apps import RETRYABLE_TASKS

        execution = get_object_or_404(TaskExecutionLog, uuid=self.kwargs['uuid'])
        action = request.POST.get('action')

        if action == 'retry':
            if execution.func_name not in RETRYABLE_TASKS.values() or not execution.func_args:
                messages.error(
                    request,
                    'No se puede reintentar: la tarea no está marcada como segura de reencolar.',
                )
                return redirect('dashboard:tasks')
            try:
                module_name, _, func_name = execution.func_name.rpartition('.')
                func = getattr(import_module(module_name), func_name)
                payload = _json.loads(execution.func_args)
                args = list(payload.get('args', []))
                kwargs = dict(payload.get('kwargs', {}))
                # Reintentar el paso que falló, no la tarea entera: si el PDF
                # ya salió bien y lo que no salió fue el correo, volver a
                # renderizar el PDF no arregla nada y lo deja con una marca de
                # tiempo nueva. La tarea es idempotente, así que
                # `_paso_a_reintentar` solo decide qué se le pide explícitamente.
                paso = _paso_a_reintentar(execution, request.POST.get('paso'))
                if paso:
                    kwargs['solo_paso'] = paso
                func(*args, **kwargs)
                messages.success(
                    request,
                    f'Tarea reencolada'
                    f'{f" (paso: {paso})" if paso else ""}. Se actualizó la misma fila.',
                )
            except Exception:
                logger.exception('No se pudo reintentar la tarea %s', execution.func_name)
                messages.error(request, 'No se pudo reintentar la tarea. Revise los logs.')
        elif action == 'delete':
            execution.delete()
            messages.success(request, f'Registro de {execution.task_name} eliminado.')
        else:
            messages.error(request, 'Acción no reconocida.')

        return redirect('dashboard:tasks')
