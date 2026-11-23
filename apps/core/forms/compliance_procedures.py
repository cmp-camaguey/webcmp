from django import forms

from apps.core.models import ComplianceProcedure


class ComplianceProcedureForm(forms.ModelForm):
    class Meta:
        model = ComplianceProcedure
        fields = ['title', 'body', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 14}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
