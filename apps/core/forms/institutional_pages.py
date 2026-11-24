import html
import re

from django import forms

from apps.core.institutional_pages import expand_schema_blocks, get_page_schema
from apps.core.models import InstitutionalPage


def _html_to_plain_text(value):
    """Convert simple rich HTML to readable plain text for textarea editing."""
    if not value:
        return ''
    text = str(value)
    if not re.search(r'<[a-zA-Z][^>]*>', text):
        return text
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'</(p|div|h[1-6]|li|tr|blockquote)>\s*', '\n', text, flags=re.I)
    text = re.sub(r'<li[^>]*>', '- ', text, flags=re.I)
    text = re.sub(r'<td[^>]*>|<th[^>]*>', ' ', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class InstitutionalPageForm(forms.ModelForm):
    class Meta:
        model = InstitutionalPage
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        schema = get_page_schema(self.instance.page_key)
        blocks = self.instance.blocks or {}
        for block in expand_schema_blocks(schema.get('blocks', []), blocks):
            name = block['name']
            field_type = block.get('type', 'char')
            label = block.get('label', name)
            if name.endswith('_icon'):
                label = 'Icono'
            elif name.startswith('card_') and name.endswith('_title'):
                label = 'Título'
            elif name.startswith('card_') and name.endswith('_text'):
                label = 'Texto'
            initial = blocks.get(name, '') or block.get('default', '')
            if field_type in ('richtext', 'textarea'):
                plain = _html_to_plain_text(initial)
                max_rows = 14 if field_type == 'richtext' else 8
                min_rows = 3 if field_type == 'richtext' else 2
                rows = max(min_rows, min(plain.count('\n') + (len(plain) // 90) + 1, max_rows))
                self.fields[name] = forms.CharField(
                    label=label,
                    required=False,
                    initial=plain,
                    widget=forms.Textarea(
                        attrs={
                            'class': 'form-control',
                            'rows': rows,
                            'style': 'overflow-y:hidden;',
                        }
                    ),
                )
            elif field_type == 'icon':
                self.fields[name] = forms.CharField(
                    label=label,
                    required=False,
                    initial=initial,
                    widget=forms.TextInput(
                        attrs={
                            'class': 'form-control icon-picker-input',
                            'data-icon-picker': 'true',
                            'autocomplete': 'off',
                        }
                    ),
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
        existing = self.instance.blocks or {}
        blocks = {}
        for block in expand_schema_blocks(schema.get('blocks', []), existing):
            name = block['name']
            value = cleaned_data.get(name, '') or ''
            field_type = block.get('type', 'char')
            default = block.get('default', '')

            if field_type in ('richtext', 'textarea'):
                value = str(value).replace('\r\n', '\n').strip()
                existing_value = existing.get(name, '')
                default_plain = _html_to_plain_text(default)
                if not existing_value and value == default_plain:
                    value = ''
                elif existing_value and value == _html_to_plain_text(existing_value):
                    value = existing_value
                blocks[name] = value
                continue

            if field_type == 'icon':
                value = value.strip()
                if value.startswith('ti ti-'):
                    value = value[3:]
                elif value and not value.startswith('ti-'):
                    value = f'ti-{value}'
            elif field_type != 'textarea':
                value = str(value).strip()

            # Keep fallback behavior if user didn't customize an empty block.
            if not existing.get(name) and value == str(default):
                value = ''
            blocks[name] = value
        self.cleaned_blocks = blocks
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.blocks = getattr(self, 'cleaned_blocks', instance.blocks or {})
        if commit:
            instance.save()
        return instance
