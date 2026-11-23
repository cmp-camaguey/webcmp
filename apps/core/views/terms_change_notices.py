import logging

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.forms.terms_change_notices import TermsChangeNoticeForm
from apps.core.models import TermsChangeNotice
from apps.core.utils import log_action

logger = logging.getLogger(__name__)


class TermsChangeNoticeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = TermsChangeNotice
    template_name = 'pages/core/terms_change_notice/list.html'
    permission_required = 'core.view_termschangenotice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Avisos de cambios legales'
        context['parent'] = ''
        context['segment'] = 'terms_change_notice'
        context['btn'] = 'Añadir aviso'
        context['url_create'] = reverse_lazy('core:terms_change_notice_create')
        context['url_list'] = reverse_lazy('core:terms_change_notice_list')
        context['objects'] = TermsChangeNotice.objects.all()
        return context


class TermsChangeNoticeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TermsChangeNotice
    form_class = TermsChangeNoticeForm
    template_name = 'pages/core/terms_change_notice/create.html'
    permission_required = 'core.add_termschangenotice'
    success_url = reverse_lazy('core:terms_change_notice_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=ADDITION,
            message=f'Se creó el aviso de cambio legal: {self.object.title}.',
        )
        messages.success(self.request, 'El aviso de cambio legal se ha creado con éxito.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear aviso de cambio legal'
        context['parent'] = ''
        context['segment'] = 'terms_change_notice'
        context['url_list'] = reverse_lazy('core:terms_change_notice_list')
        return context


class TermsChangeNoticeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = TermsChangeNotice
    form_class = TermsChangeNoticeForm
    template_name = 'pages/core/terms_change_notice/update.html'
    permission_required = 'core.change_termschangenotice'
    success_url = reverse_lazy('core:terms_change_notice_list')

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        return get_object_or_404(TermsChangeNotice, uuid=pk)

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=CHANGE,
            message=f'Se actualizó el aviso de cambio legal: {self.object.title}.',
        )
        messages.success(self.request, 'El aviso de cambio legal se ha actualizado con éxito.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Actualizar aviso de cambio legal'
        context['parent'] = ''
        context['segment'] = 'terms_change_notice'
        context['url_list'] = reverse_lazy('core:terms_change_notice_list')
        return context


class TermsChangeNoticeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.delete_termschangenotice'

    def post(self, request, pk):
        obj = get_object_or_404(TermsChangeNotice, uuid=pk)
        title = obj.title
        log_action(
            user=request.user,
            obj=obj,
            action_flag=DELETION,
            message=f'Se eliminó el aviso de cambio legal: {title}.',
        )
        obj.delete()
        messages.success(request, 'El aviso de cambio legal se ha eliminado con éxito.')
        return redirect('core:terms_change_notice_list')
