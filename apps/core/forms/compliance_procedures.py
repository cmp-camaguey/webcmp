from django import forms

from apps.core.models import ComplianceProcedure
from apps.core.sanitize import sanitize_html


class ComplianceProcedureForm(forms.ModelForm):
    class Meta:
        model = ComplianceProcedure
        fields = ['title', 'body', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'body': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 14,
                    'data-richtext': 'true',
                }
            ),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_body(self):
        return sanitize_html(self.cleaned_data.get('body', ''))
