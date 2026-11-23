import logging

from django.contrib import messages
from django.contrib.admin.models import CHANGE
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView

from apps.core.forms.compliance_procedures import ComplianceProcedureForm
from apps.core.models import ComplianceProcedure
from apps.core.utils import log_action

logger = logging.getLogger(__name__)


class ComplianceProcedureListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ComplianceProcedure
    template_name = 'pages/core/compliance_procedure/list.html'
    permission_required = 'core.view_complianceprocedure'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Procedimientos de cumplimiento'
        context['parent'] = ''
        context['segment'] = 'compliance_procedure'
        context['url_list'] = reverse_lazy('core:compliance_procedure_list')
        context['objects'] = ComplianceProcedure.objects.all()
        return context


class ComplianceProcedureUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ComplianceProcedure
    form_class = ComplianceProcedureForm
    template_name = 'pages/core/compliance_procedure/update.html'
    permission_required = 'core.change_complianceprocedure'
    success_url = reverse_lazy('core:compliance_procedure_list')

    def get_object(self, queryset=None):
        return get_object_or_404(ComplianceProcedure, uuid=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Editar: {self.object.get_procedure_type_display()}'
        context['parent'] = ''
        context['segment'] = 'compliance_procedure'
        context['url_list'] = reverse_lazy('core:compliance_procedure_list')
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=CHANGE,
            message=f'Se actualizó el procedimiento de cumplimiento: {self.object}.',
        )
        messages.success(self.request, 'El procedimiento se ha actualizado con éxito.')
        return response
