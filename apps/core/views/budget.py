import logging

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.forms.budget import BudgetLineFormSet, BudgetPeriodForm
from apps.core.models import BudgetPeriod
from apps.core.utils import log_action

logger = logging.getLogger(__name__)


class BudgetPeriodListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = BudgetPeriod
    template_name = 'pages/core/budget/list.html'
    permission_required = 'core.view_budgetperiod'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Presupuestos'
        context['parent'] = ''
        context['segment'] = 'budget_period'
        context['btn'] = 'Añadir período'
        context['url_create'] = reverse_lazy('core:budget_period_create')
        context['url_list'] = reverse_lazy('core:budget_period_list')
        context['objects'] = BudgetPeriod.objects.prefetch_related('lines').all()
        return context


class BudgetPeriodCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = BudgetPeriod
    form_class = BudgetPeriodForm
    template_name = 'pages/core/budget/create.html'
    permission_required = 'core.add_budgetperiod'
    success_url = reverse_lazy('core:budget_period_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = kwargs.get(
            'formset', BudgetLineFormSet(instance=self.object, prefix='lines')
        )
        context['title'] = 'Crear período presupuestario'
        context['parent'] = ''
        context['segment'] = 'budget_period'
        context['url_list'] = reverse_lazy('core:budget_period_list')
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        formset = BudgetLineFormSet(self.request.POST, instance=self.object, prefix='lines')
        if formset.is_valid():
            formset.save()
            log_action(
                user=self.request.user,
                obj=self.object,
                action_flag=ADDITION,
                message=f'Se creó el período presupuestario: {self.object}.',
            )
            messages.success(self.request, 'El período presupuestario se ha creado con éxito.')
            return response
        self.object.delete()
        return self.render_to_response(self.get_context_data(form=form, formset=formset))


class BudgetPeriodUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = BudgetPeriod
    form_class = BudgetPeriodForm
    template_name = 'pages/core/budget/update.html'
    permission_required = 'core.change_budgetperiod'
    success_url = reverse_lazy('core:budget_period_list')

    def get_object(self, queryset=None):
        return get_object_or_404(BudgetPeriod, pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = kwargs.get(
            'formset', BudgetLineFormSet(instance=self.object, prefix='lines')
        )
        context['title'] = 'Actualizar período presupuestario'
        context['parent'] = ''
        context['segment'] = 'budget_period'
        context['url_list'] = reverse_lazy('core:budget_period_list')
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        formset = BudgetLineFormSet(self.request.POST, instance=self.object, prefix='lines')
        if formset.is_valid():
            formset.save()
            log_action(
                user=self.request.user,
                obj=self.object,
                action_flag=CHANGE,
                message=f'Se actualizó el período presupuestario: {self.object}.',
            )
            messages.success(self.request, 'El período presupuestario se ha actualizado con éxito.')
            return response
        return self.render_to_response(self.get_context_data(form=form, formset=formset))


class BudgetPeriodDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.delete_budgetperiod'

    def post(self, request, pk):
        obj = get_object_or_404(BudgetPeriod, pk=pk)
        title = str(obj)
        log_action(
            user=request.user,
            obj=obj,
            action_flag=DELETION,
            message=f'Se eliminó el período presupuestario: {title}.',
        )
        obj.delete()
        messages.success(request, 'El período presupuestario se ha eliminado con éxito.')
        return redirect('core:budget_period_list')
