from django import forms

from apps.core.models import TermsChangeNotice


class TermsChangeNoticeForm(forms.ModelForm):
    class Meta:
        model = TermsChangeNotice
        fields = ['title', 'description', 'affected_document', 'effective_date', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'affected_document': forms.Select(attrs={'class': 'form-select'}),
            'effective_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
