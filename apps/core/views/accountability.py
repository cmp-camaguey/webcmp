import logging

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.forms.accountability import AccountabilityReportForm
from apps.core.models import AccountabilityReport
from apps.core.utils import log_action

logger = logging.getLogger(__name__)


class AccountabilityReportListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AccountabilityReport
    template_name = 'pages/core/accountability/list.html'
    permission_required = 'core.view_accountabilityreport'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Informes de rendición de cuenta'
        context['parent'] = ''
        context['segment'] = 'accountability_report'
        context['btn'] = 'Añadir informe'
        context['url_create'] = reverse_lazy('core:accountability_report_create')
        context['url_list'] = reverse_lazy('core:accountability_report_list')
        context['objects'] = AccountabilityReport.objects.all()
        return context


class AccountabilityReportCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = AccountabilityReport
    form_class = AccountabilityReportForm
    template_name = 'pages/core/accountability/create.html'
    permission_required = 'core.add_accountabilityreport'
    success_url = reverse_lazy('core:accountability_report_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear informe de rendición de cuenta'
        context['parent'] = ''
        context['segment'] = 'accountability_report'
        context['url_list'] = reverse_lazy('core:accountability_report_list')
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=ADDITION,
            message=f'Se creó el informe de rendición de cuenta: {self.object}.',
        )
        messages.success(self.request, 'El informe se ha creado con éxito.')
        return response


class AccountabilityReportUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = AccountabilityReport
    form_class = AccountabilityReportForm
    template_name = 'pages/core/accountability/update.html'
    permission_required = 'core.change_accountabilityreport'
    success_url = reverse_lazy('core:accountability_report_list')

    def get_object(self, queryset=None):
        return get_object_or_404(AccountabilityReport, pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Actualizar informe de rendición de cuenta'
        context['parent'] = ''
        context['segment'] = 'accountability_report'
        context['url_list'] = reverse_lazy('core:accountability_report_list')
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=CHANGE,
            message=f'Se actualizó el informe de rendición de cuenta: {self.object}.',
        )
        messages.success(self.request, 'El informe se ha actualizado con éxito.')
        return response


class AccountabilityReportDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.delete_accountabilityreport'

    def post(self, request, pk):
        obj = get_object_or_404(AccountabilityReport, pk=pk)
        title = str(obj)
        log_action(
            user=request.user,
            obj=obj,
            action_flag=DELETION,
            message=f'Se eliminó el informe de rendición de cuenta: {title}.',
        )
        obj.delete()
        messages.success(request, 'El informe se ha eliminado con éxito.')
        return redirect('core:accountability_report_list')
