from django import forms

from apps.core.models import AccountabilityReport


class AccountabilityReportForm(forms.ModelForm):
    class Meta:
        model = AccountabilityReport
        fields = ['year', 'title', 'description', 'file', 'is_published']
        widgets = {
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
