"""Dashboard comercial por perfil (042)."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from apps.dashboard.services.commercial_dashboard import (
    get_commercial_dashboard_context,
    has_commercial_dashboard_access,
    normalize_income_range,
)


class CommercialDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'pages/dashboard/commercial.html'

    def test_func(self):
        return has_commercial_dashboard_access(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        income_range = normalize_income_range(self.request.GET.get('income_range'))
        context.update(
            get_commercial_dashboard_context(self.request.user, income_range=income_range)
        )
        context.update(
            {
                'title': 'Resumen Comercial',
                'parent': 'Dashboard',
                'segment': 'dashboard_comercial',
            }
        )
        return context
