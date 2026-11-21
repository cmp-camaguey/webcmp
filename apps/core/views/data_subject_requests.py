import logging

from django.contrib import messages
from django.contrib.admin.models import CHANGE
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView

from apps.core.models import DataSubjectRequest
from apps.core.utils import log_action

logger = logging.getLogger(__name__)


class DataSubjectRequestListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DataSubjectRequest
    template_name = 'pages/core/data_subject_request/list.html'
    permission_required = 'core.view_datasubjectrequest'
    context_object_name = 'objects'

    def get_queryset(self):
        return DataSubjectRequest.objects.all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Solicitudes de derechos ARCO/ARCOP'
        context['parent'] = ''
        context['segment'] = 'data_subject_request'
        context['url_list'] = reverse_lazy('core:data_subject_request_list')
        context['is_superuser'] = self.request.user.is_superuser
        return context


class DataSubjectRequestUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = DataSubjectRequest
    fields = ['status', 'admin_notes']
    template_name = 'pages/core/data_subject_request/update.html'
    permission_required = 'core.change_datasubjectrequest'
    success_url = reverse_lazy('core:data_subject_request_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['status'].widget.attrs.update({'class': 'form-select'})
        form.fields['admin_notes'].widget.attrs.update(
            {
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notas internas sobre la gestión de esta solicitud',
            }
        )
        form.fields['admin_notes'].required = False
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Gestionar solicitud de derechos'
        context['parent'] = ''
        context['segment'] = 'data_subject_request'
        context['url_list'] = reverse_lazy('core:data_subject_request_list')
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=CHANGE,
            message=(
                f'Se actualizó la solicitud de derechos {self.object.uuid} '
                f'({self.object.get_request_type_display()}) a estado '
                f'{self.object.get_status_display()}.'
            ),
        )
        messages.success(self.request, 'La solicitud ha sido actualizada con éxito.')
        return response
