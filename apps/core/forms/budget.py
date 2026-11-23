from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.models import BudgetLine, BudgetPeriod


class BudgetPeriodForm(forms.ModelForm):
    class Meta:
        model = BudgetPeriod
        fields = ['year', 'title', 'description', 'is_published']
        widgets = {
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BudgetLineForm(forms.ModelForm):
    class Meta:
        model = BudgetLine
        fields = ['category', 'planned_amount', 'executed_amount', 'order']
        widgets = {
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Partida'}),
            'planned_amount': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}
            ),
            'executed_amount': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}
            ),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class BaseBudgetLineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        has_line = False
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            if form.cleaned_data.get('category'):
                has_line = True
                break
        if not has_line:
            raise forms.ValidationError('Agregue al menos una partida presupuestaria.')


BudgetLineFormSet = inlineformset_factory(
    BudgetPeriod,
    BudgetLine,
    form=BudgetLineForm,
    formset=BaseBudgetLineFormSet,
    extra=1,
    can_delete=True,
)
