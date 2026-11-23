from django import forms

from apps.core.institutional_pages import get_page_schema
from apps.core.models import InstitutionalPage
from apps.core.sanitize import sanitize_html


class InstitutionalPageForm(forms.ModelForm):
    class Meta:
        model = InstitutionalPage
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        schema = get_page_schema(self.instance.page_key)
        blocks = self.instance.blocks or {}
        for block in schema.get('blocks', []):
            name = block['name']
            field_type = block.get('type', 'char')
            label = block.get('label', name)
            initial = blocks.get(name, '')
            if field_type == 'richtext':
                self.fields[name] = forms.CharField(
                    label=label,
                    required=False,
                    initial=initial,
                    widget=forms.Textarea(
                        attrs={'class': 'form-control', 'rows': 10, 'data-richtext': 'true'}
                    ),
                )
            elif field_type == 'textarea':
                self.fields[name] = forms.CharField(
                    label=label,
                    required=False,
                    initial=initial,
                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
                )
            else:
                self.fields[name] = forms.CharField(
                    label=label,
                    required=False,
                    initial=initial,
                    widget=forms.TextInput(attrs={'class': 'form-control'}),
                )

    def clean(self):
        cleaned_data = super().clean()
        schema = get_page_schema(self.instance.page_key)
        blocks = {}
        for block in schema.get('blocks', []):
            name = block['name']
            value = cleaned_data.get(name, '') or ''
            if block.get('type') == 'richtext':
                value = sanitize_html(value)
            blocks[name] = value
        self.cleaned_blocks = blocks
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.blocks = getattr(self, 'cleaned_blocks', instance.blocks or {})
        if commit:
            instance.save()
        return instance
