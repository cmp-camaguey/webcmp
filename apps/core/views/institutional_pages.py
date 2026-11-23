import logging

from django.contrib import messages
from django.contrib.admin.models import CHANGE
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView

from apps.core.forms.institutional_pages import InstitutionalPageForm
from apps.core.institutional_pages import get_page_schema
from apps.core.models import InstitutionalPage
from apps.core.utils import log_action

logger = logging.getLogger(__name__)


class InstitutionalPageListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = InstitutionalPage
    template_name = 'pages/core/institutional_page/list.html'
    permission_required = 'core.view_institutionalpage'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Páginas institucionales'
        context['parent'] = ''
        context['segment'] = 'institutional_page'
        context['url_list'] = reverse_lazy('core:institutional_page_list')
        context['objects'] = InstitutionalPage.objects.all()
        return context


class InstitutionalPageUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = InstitutionalPage
    form_class = InstitutionalPageForm
    template_name = 'pages/core/institutional_page/update.html'
    permission_required = 'core.change_institutionalpage'
    success_url = reverse_lazy('core:institutional_page_list')

    def get_object(self, queryset=None):
        return get_object_or_404(InstitutionalPage, uuid=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schema = get_page_schema(self.object.page_key)
        context['title'] = f'Editar: {self.object.get_page_key_display()}'
        context['parent'] = ''
        context['segment'] = 'institutional_page'
        context['url_list'] = reverse_lazy('core:institutional_page_list')
        context['schema_blocks'] = schema.get('blocks', [])
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            user=self.request.user,
            obj=self.object,
            action_flag=CHANGE,
            message=f'Se actualizó el contenido institucional: {self.object}.',
        )
        messages.success(self.request, 'El contenido se ha actualizado con éxito.')
        return response
