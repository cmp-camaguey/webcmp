import logging

from django.contrib import messages
from django.contrib.admin.models import CHANGE
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, UpdateView

from apps.core.forms.institutional_pages import InstitutionalPageForm
from apps.core.institutional_pages import expand_schema_blocks, get_page_schema
from apps.core.models import InstitutionalPage
from apps.core.utils import log_action

logger = logging.getLogger(__name__)

PUBLIC_PAGE_URLS = {
    'vision': 'home:institution_vision',
    'mission': 'home:institution_mission',
    'about': 'home:institution_about',
    'institutional_information': 'home:institution_information',
    'legal_notice': 'home:institution_legal_notice',
    'privacy_policy': 'home:institution_privacy_policy',
    'cookie_policy': 'home:institution_cookie_policy',
    'data_subject_rights': 'home:institution_data_subject_rights',
}


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
        context['has_cards'] = any(b.get('type') == 'card_set' for b in schema.get('blocks', []))
        schema_blocks = expand_schema_blocks(schema.get('blocks', []), self.object.blocks or {})
        groups = [b.get('group', '') for b in schema_blocks]
        card_group_count = len({g for g in groups if g.startswith('Tarjeta')})
        card_col_class = 'col-12 col-md-6 col-xl-4' if card_group_count == 3 else 'col-12 col-xl-6'
        blocks = []
        group_ids = {}
        for i, block in enumerate(schema_blocks):
            item = dict(block)
            group = item.get('group', '')
            if group and group not in group_ids:
                group_ids[group] = len(group_ids)
            item['group_id'] = f'group-{group_ids[group]}' if group else ''
            prev_group = groups[i - 1] if i > 0 else None
            next_group = groups[i + 1] if i + 1 < len(groups) else None
            is_card = group.startswith('Tarjeta')
            prev_is_card = bool(prev_group and prev_group.startswith('Tarjeta'))
            next_is_card = bool(next_group and next_group.startswith('Tarjeta'))
            group_start = group != prev_group
            group_end = group != next_group
            item['is_card_group'] = is_card
            item['prev_is_card_group'] = prev_is_card
            item['card_grid_open'] = is_card and group_start and not prev_is_card
            item['card_grid_close'] = is_card and group_end and not next_is_card
            item['card_col_open'] = is_card and group_start
            item['card_col_close'] = is_card and group_end
            item['card_col_class'] = card_col_class if is_card else ''

            row_set = item.get('row_set')
            prev_row_set = schema_blocks[i - 1].get('row_set') if i > 0 else None
            next_row_set = (
                schema_blocks[i + 1].get('row_set') if i + 1 < len(schema_blocks) else None
            )
            prev_row_index = schema_blocks[i - 1].get('row_index') if i > 0 else None
            next_row_index = (
                schema_blocks[i + 1].get('row_index')
                if i + 1 < len(schema_blocks) and schema_blocks[i + 1].get('row_set')
                else None
            )
            item['is_row_set'] = bool(row_set)
            item['row_set_start'] = bool(row_set) and row_set != prev_row_set
            item['row_set_end'] = bool(row_set) and row_set != next_row_set
            item['row_start'] = bool(row_set) and item.get('row_index') != prev_row_index
            item['row_end'] = bool(row_set) and (
                row_set != next_row_set or item.get('row_index') != next_row_index
            )

            item['row_open'] = False
            item['row_close'] = False
            item['col_class'] = ''
            if not is_card:
                field_type = item.get('type', 'char')
                next_block = schema_blocks[i + 1] if i + 1 < len(schema_blocks) else {}
                next_in_group = next_group == group
                next_type = next_block.get('type', 'char')
                prev_was_pair_start = bool(
                    i > 0 and blocks and blocks[-1].get('row_open') and prev_group == group
                )
                next_name = next_block.get('name', '')
                pair_start = (
                    not prev_was_pair_start
                    and field_type == 'char'
                    and next_in_group
                    and next_type in ('char', 'textarea')
                    and item.get('name', '').endswith('_title')
                    and next_name.endswith('_intro')
                )
                pair_end = prev_was_pair_start
                item['row_open'] = pair_start
                item['row_close'] = pair_end
                if pair_start:
                    item['col_class'] = 'col-12 col-lg-4'
                elif pair_end:
                    item['col_class'] = 'col-12 col-lg-8'

            if item['row_set_start']:
                row_set_block = next(
                    (b for b in schema.get('blocks', []) if b.get('name') == row_set),
                    {},
                )
                item['row_columns'] = row_set_block.get('fields', [])
                item['row_table_layout'] = row_set_block.get('table_layout', 'fixed')

            section_set = item.get('section_set')
            item['is_section_set'] = bool(section_set)
            item['section_set_start'] = bool(section_set) and group_start
            item['section_set_end'] = bool(section_set) and group_end

            blocks.append(item)
        context['schema_blocks'] = blocks
        context['has_rows'] = any(b.get('type') == 'row_set' for b in schema.get('blocks', []))
        section_set_block = next(
            (b for b in schema.get('blocks', []) if b.get('type') == 'section_set'),
            None,
        )
        context['has_sections'] = bool(section_set_block)
        context['section_set_name'] = (
            section_set_block.get('name', 'extra_sections') if section_set_block else ''
        )
        context['collapsible_groups'] = self.object.page_key in {
            'cookie_policy',
            'privacy_policy',
        }
        public_url_name = PUBLIC_PAGE_URLS.get(self.object.page_key)
        context['public_page_url'] = reverse(public_url_name) if public_url_name else None
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if (
            'add_card' in request.POST
            or 'remove_card' in request.POST
            or 'add_row' in request.POST
            or 'remove_row' in request.POST
            or 'add_section' in request.POST
            or 'remove_section' in request.POST
        ):
            form = self.get_form()
            if form.is_valid():
                form.save()
                blocks = dict(self.object.blocks or {})
                schema = get_page_schema(self.object.page_key)

                if 'add_card' in request.POST or 'remove_card' in request.POST:
                    set_block = next(
                        (b for b in schema.get('blocks', []) if b.get('type') == 'card_set'),
                        None,
                    )
                    prefix = 'card'
                    label = 'tarjeta'
                elif 'add_section' in request.POST or 'remove_section' in request.POST:
                    prefix = (
                        request.POST.get('add_section')
                        or str(request.POST.get('remove_section', '')).split(':', 1)[0]
                    )
                    set_block = next(
                        (
                            b
                            for b in schema.get('blocks', [])
                            if b.get('type') == 'section_set'
                            and b.get('name', 'sections') == prefix
                        ),
                        None,
                    )
                    label = 'punto'
                else:
                    prefix = (
                        request.POST.get('add_row')
                        or str(request.POST.get('remove_row', '')).split(':', 1)[0]
                    )
                    set_block = next(
                        (
                            b
                            for b in schema.get('blocks', [])
                            if b.get('type') == 'row_set' and b.get('name', 'rows') == prefix
                        ),
                        None,
                    )
                    label = 'fila'

                if set_block:
                    fields = set_block.get('fields', [])
                    max_n = 0
                    for key in blocks:
                        parts = key.split('_')
                        # card_N_suffix or prefix_N_suffix
                        if prefix == 'card':
                            if key.startswith('card_') and len(parts) > 1 and parts[1].isdigit():
                                max_n = max(max_n, int(parts[1]))
                        elif (
                            key.startswith(f'{prefix}_') and len(parts) > 2 and parts[-2].isdigit()
                        ):
                            max_n = max(max_n, int(parts[-2]))

                    if (
                        'add_card' in request.POST
                        or 'add_row' in request.POST
                        or 'add_section' in request.POST
                    ):
                        next_n = max_n + 1
                        for field in fields:
                            suffix = field['suffix']
                            key = (
                                f'card_{next_n}_{suffix}'
                                if prefix == 'card'
                                else f'{prefix}_{next_n}_{suffix}'
                            )
                            blocks[key] = ''
                        msg = f'Se agregó una nueva {label}.'
                        log_msg = f'Se agregó una {label} en: {self.object}.'
                    else:
                        raw_remove = (
                            request.POST.get('remove_card')
                            or request.POST.get('remove_row')
                            or request.POST.get('remove_section', '')
                        )
                        raw_remove = str(raw_remove).split(':')[-1]
                        try:
                            remove_n = int(raw_remove)
                        except TypeError, ValueError:
                            remove_n = 0
                        if remove_n > 0:
                            for field in fields:
                                suffix = field['suffix']
                                key = (
                                    f'card_{remove_n}_{suffix}'
                                    if prefix == 'card'
                                    else f'{prefix}_{remove_n}_{suffix}'
                                )
                                blocks.pop(key, None)
                            remaining = []
                            for i in range(1, max_n + 1):
                                if i == remove_n:
                                    continue
                                item = {}
                                for field in fields:
                                    suffix = field['suffix']
                                    k = (
                                        f'card_{i}_{suffix}'
                                        if prefix == 'card'
                                        else f'{prefix}_{i}_{suffix}'
                                    )
                                    if k in blocks:
                                        item[suffix] = blocks.pop(k)
                                if item:
                                    remaining.append(item)
                            for idx, item in enumerate(remaining, start=1):
                                for suffix, val in item.items():
                                    k = (
                                        f'card_{idx}_{suffix}'
                                        if prefix == 'card'
                                        else f'{prefix}_{idx}_{suffix}'
                                    )
                                    blocks[k] = val
                        msg = f'Se eliminó la {label}.'
                        log_msg = f'Se eliminó una {label} en: {self.object}.'

                    self.object.blocks = blocks
                    self.object.save(update_fields=['blocks'])
                    log_action(
                        user=self.request.user,
                        obj=self.object,
                        action_flag=CHANGE,
                        message=log_msg,
                    )
                    messages.success(self.request, msg)
                return redirect('core:institutional_page_update', pk=self.object.uuid)
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

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
