from django import forms
from django.contrib import messages
from django.contrib.admin.models import CHANGE
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView

from apps.core.models import ActivityLog, PublicInformationRequest
from apps.core.utils import log_action


class PublicInformationRequestListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PublicInformationRequest
    template_name = 'pages/core/public_information_request/list.html'
    permission_required = 'core.view_publicinformationrequest'
    context_object_name = 'objects'

    def get_queryset(self):
        return PublicInformationRequest.objects.select_related('responsible').order_by(
            '-created_at'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Solicitudes de información pública'
        context['parent'] = ''
        context['segment'] = 'public_information_request'
        context['url_list'] = reverse_lazy('core:public_information_request_list')
        context['is_superuser'] = self.request.user.is_superuser
        return context


class PublicInformationRequestForm(forms.ModelForm):
    class Meta:
        model = PublicInformationRequest
        fields = [
            'status',
            'responsible',
            'due_date',
            'delivery_date',
            'delivery_format',
            'response_attachment',
            'rejection_reason',
            'admin_notes',
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'responsible': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_format': forms.Select(attrs={'class': 'form-select'}),
            'response_attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'rejection_reason': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Indique la causa del rechazo',
                }
            ),
            'admin_notes': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Notas internas sobre la gestión de esta solicitud',
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        responsible = cleaned_data.get('responsible')
        admin_notes = (cleaned_data.get('admin_notes') or '').strip()
        delivery_date = cleaned_data.get('delivery_date')
        delivery_format = cleaned_data.get('delivery_format')
        rejection_reason = (cleaned_data.get('rejection_reason') or '').strip()

        if status == PublicInformationRequest.Status.EN_PROCESO:
            if not responsible:
                self.add_error(
                    'responsible',
                    'Seleccione un responsable para gestionar la solicitud.',
                )
            if not admin_notes:
                self.add_error('admin_notes', 'Indique la nota de gestión.')
        elif status == PublicInformationRequest.Status.COMPLETADA:
            if not delivery_date:
                self.add_error('delivery_date', 'Indique la fecha de entrega.')
            if not delivery_format:
                self.add_error('delivery_format', 'Indique el canal real de entrega.')
            if not admin_notes:
                self.add_error('admin_notes', 'Indique la nota o respuesta entregada.')
        elif status == PublicInformationRequest.Status.RECHAZADA and not rejection_reason:
            self.add_error('rejection_reason', 'Indique la causa del rechazo.')

        cleaned_data['admin_notes'] = admin_notes
        cleaned_data['rejection_reason'] = rejection_reason
        return cleaned_data


class PublicInformationRequestUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PublicInformationRequest
    form_class = PublicInformationRequestForm
    template_name = 'pages/core/public_information_request/update.html'
    permission_required = 'core.change_publicinformationrequest'
    success_url = reverse_lazy('core:public_information_request_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Gestionar solicitud de información pública'
        context['parent'] = ''
        context['segment'] = 'public_information_request'
        context['url_list'] = reverse_lazy('core:public_information_request_list')
        content_type = ContentType.objects.get_for_model(PublicInformationRequest)
        context['history'] = (
            ActivityLog.objects.filter(content_type=content_type, object_id=str(self.object.pk))
            .select_related('user')
            .order_by('-action_time')[:20]
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=CHANGE,
            message=(
                f'Se actualizó la solicitud de información pública {self.object.uuid} '
                f'a estado {self.object.get_status_display()}.'
            ),
        )
        messages.success(self.request, 'La solicitud ha sido actualizada con éxito.')
        return response
