"""Dashboard de sistema por perfil (044)."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from apps.dashboard.services.system_dashboard import (
    get_system_dashboard_context,
    has_system_dashboard_access,
)


class SystemDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'pages/dashboard/sistema.html'

    def test_func(self):
        return has_system_dashboard_access(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_system_dashboard_context(self.request.user))
        context.update(
            {
                'title': 'Resumen del Sistema',
                'parent': 'Dashboard',
                'segment': 'dashboard_sistema',
            }
        )
        return context
