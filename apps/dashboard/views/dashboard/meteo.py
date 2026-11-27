"""Dashboard meteorológico por perfil (043)."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from apps.dashboard.services.meteo_dashboard import (
    get_meteo_dashboard_context,
    has_meteo_dashboard_access,
    normalize_meteo_range,
)


class MeteoDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'pages/dashboard/meteorologia.html'

    def test_func(self):
        return has_meteo_dashboard_access(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_range = normalize_meteo_range(self.request.GET.get('range'))
        context.update(get_meteo_dashboard_context(range=selected_range))
        user = self.request.user
        context.update(
            {
                'title': 'Resumen Meteorológico',
                'parent': 'Dashboard',
                'segment': 'dashboard_meteo',
                'show_forecast': user.has_perm('meteo.view_forecast'),
                'show_alerts': user.has_perm('meteo.view_warning'),
            }
        )
        return context
