"""Fixed schemas for dashboard-editable institutional pages.

The template owns structure; the dashboard edits only these predefined blocks.
"""

PAGE_SCHEMAS = {
    'vision': {
        'title': 'Visión',
        'blocks': [
            {'name': 'hero_description', 'label': 'Descripción principal', 'type': 'textarea'},
            {'name': 'section_title', 'label': 'Título de sección', 'type': 'char'},
            {'name': 'section_description', 'label': 'Descripción de sección', 'type': 'textarea'},
            {'name': 'card_1_title', 'label': 'Valor 1 - Título', 'type': 'char'},
            {'name': 'card_1_text', 'label': 'Valor 1 - Texto', 'type': 'textarea'},
            {'name': 'card_2_title', 'label': 'Valor 2 - Título', 'type': 'char'},
            {'name': 'card_2_text', 'label': 'Valor 2 - Texto', 'type': 'textarea'},
            {'name': 'card_3_title', 'label': 'Valor 3 - Título', 'type': 'char'},
            {'name': 'card_3_text', 'label': 'Valor 3 - Texto', 'type': 'textarea'},
            {'name': 'card_4_title', 'label': 'Valor 4 - Título', 'type': 'char'},
            {'name': 'card_4_text', 'label': 'Valor 4 - Texto', 'type': 'textarea'},
        ],
    },
    'mission': {
        'title': 'Misión',
        'blocks': [
            {
                'name': 'hero_paragraph_1',
                'label': 'Descripción principal - Párrafo 1',
                'type': 'textarea',
            },
            {
                'name': 'hero_paragraph_2',
                'label': 'Descripción principal - Párrafo 2',
                'type': 'textarea',
            },
            {'name': 'section_title', 'label': 'Título de sección', 'type': 'char'},
            {'name': 'section_description', 'label': 'Descripción de sección', 'type': 'textarea'},
            {'name': 'card_1_title', 'label': 'Compromiso 1 - Título', 'type': 'char'},
            {'name': 'card_1_text', 'label': 'Compromiso 1 - Texto', 'type': 'textarea'},
            {'name': 'card_2_title', 'label': 'Compromiso 2 - Título', 'type': 'char'},
            {'name': 'card_2_text', 'label': 'Compromiso 2 - Texto', 'type': 'textarea'},
            {'name': 'card_3_title', 'label': 'Compromiso 3 - Título', 'type': 'char'},
            {'name': 'card_3_text', 'label': 'Compromiso 3 - Texto', 'type': 'textarea'},
            {'name': 'card_4_title', 'label': 'Compromiso 4 - Título', 'type': 'char'},
            {'name': 'card_4_text', 'label': 'Compromiso 4 - Texto', 'type': 'textarea'},
        ],
    },
    'about': {
        'title': 'Quiénes somos',
        'blocks': [
            {
                'name': 'hero_paragraph_1',
                'label': 'Descripción principal - Párrafo 1',
                'type': 'textarea',
            },
            {
                'name': 'hero_paragraph_2',
                'label': 'Descripción principal - Párrafo 2',
                'type': 'textarea',
            },
            {'name': 'section_title', 'label': 'Título de sección', 'type': 'char'},
            {'name': 'section_description', 'label': 'Descripción de sección', 'type': 'textarea'},
            {'name': 'card_1_title', 'label': 'Tarjeta 1 - Título', 'type': 'char'},
            {'name': 'card_1_text', 'label': 'Tarjeta 1 - Texto', 'type': 'textarea'},
            {'name': 'card_2_title', 'label': 'Tarjeta 2 - Título', 'type': 'char'},
            {'name': 'card_2_text', 'label': 'Tarjeta 2 - Texto', 'type': 'textarea'},
            {'name': 'card_3_title', 'label': 'Tarjeta 3 - Título', 'type': 'char'},
            {'name': 'card_3_text', 'label': 'Tarjeta 3 - Texto', 'type': 'textarea'},
        ],
    },
    'institutional_information': {
        'title': 'Información institucional',
        'blocks': [
            {'name': 'hero_description', 'label': 'Descripción principal', 'type': 'textarea'},
            {'name': 'org_title', 'label': 'Estructura organizativa - Título', 'type': 'char'},
            {
                'name': 'org_description',
                'label': 'Estructura organizativa - Descripción',
                'type': 'textarea',
            },
            {
                'name': 'org_body',
                'label': 'Estructura organizativa - Contenido',
                'type': 'richtext',
            },
            {'name': 'directors_title', 'label': 'Directivos - Título', 'type': 'char'},
            {
                'name': 'directors_description',
                'label': 'Directivos - Descripción',
                'type': 'textarea',
            },
            {'name': 'directors_body', 'label': 'Directivos - Contenido', 'type': 'richtext'},
            {'name': 'strategy_title', 'label': 'Estrategia - Título', 'type': 'char'},
            {'name': 'strategy_body', 'label': 'Estrategia - Contenido', 'type': 'richtext'},
        ],
    },
    'legal_notice': {
        'title': 'Aviso legal',
        'blocks': [
            {'name': 'hero_description', 'label': 'Descripción principal', 'type': 'textarea'},
            {'name': 'card_title', 'label': 'Título de la tarjeta', 'type': 'char'},
            {
                'name': 'institutional_condition',
                'label': 'Condición institucional',
                'type': 'textarea',
            },
            {'name': 'footer_note', 'label': 'Nota final', 'type': 'textarea'},
        ],
    },
    'data_subject_rights': {
        'title': 'Derechos del titular',
        'blocks': [
            {'name': 'hero_description', 'label': 'Descripción principal', 'type': 'textarea'},
            {'name': 'form_intro', 'label': 'Introducción del formulario', 'type': 'richtext'},
            {'name': 'after_submit_title', 'label': 'Título "Qué pasa después"', 'type': 'char'},
            {
                'name': 'after_submit_body',
                'label': 'Contenido "Qué pasa después"',
                'type': 'richtext',
            },
            {'name': 'rights_title', 'label': 'Título información de derechos', 'type': 'char'},
            {
                'name': 'rights_intro',
                'label': 'Introducción información de derechos',
                'type': 'textarea',
            },
            {
                'name': 'rights_body',
                'label': 'Contenido información de derechos',
                'type': 'richtext',
            },
        ],
    },
    'cookie_policy': {
        'title': 'Política de cookies',
        'blocks': [
            {'name': 'hero_description', 'label': 'Descripción principal', 'type': 'textarea'},
            {'name': 'section_que_son', 'label': '1. ¿Qué son las cookies?', 'type': 'richtext'},
            {
                'name': 'section_categorias',
                'label': '2. Categorías de cookies que usamos',
                'type': 'richtext',
            },
            {
                'name': 'section_detalle',
                'label': '3. Detalle de cookies utilizadas',
                'type': 'richtext',
            },
            {
                'name': 'section_consentimiento',
                'label': '4. Cómo gestionar tu consentimiento',
                'type': 'richtext',
            },
            {
                'name': 'section_desactivar',
                'label': '5. Cómo desactivar o borrar cookies desde el navegador',
                'type': 'richtext',
            },
            {'name': 'section_contacto', 'label': '6. Responsable y contacto', 'type': 'richtext'},
            {'name': 'section_actualizaciones', 'label': '7. Actualizaciones', 'type': 'richtext'},
        ],
    },
    'privacy_policy': {
        'title': 'Política de privacidad',
        'blocks': [
            {'name': 'hero_description', 'label': 'Descripción principal', 'type': 'textarea'},
            {
                'name': 'section_responsable',
                'label': '1. Responsable del tratamiento',
                'type': 'richtext',
            },
            {
                'name': 'section_datos',
                'label': '2. Datos que tratamos y finalidad',
                'type': 'richtext',
            },
            {'name': 'section_destinatarios', 'label': '3. Destinatarios', 'type': 'richtext'},
            {
                'name': 'section_transferencias',
                'label': '4. Transferencias internacionales',
                'type': 'richtext',
            },
            {
                'name': 'section_conservacion',
                'label': '5. Plazos de conservación',
                'type': 'richtext',
            },
            {'name': 'section_derechos', 'label': '6. Derechos del titular', 'type': 'richtext'},
            {'name': 'section_seguridad', 'label': '7. Medidas de seguridad', 'type': 'richtext'},
            {'name': 'section_actualizaciones', 'label': '8. Actualizaciones', 'type': 'richtext'},
        ],
    },
}


def get_page_schema(page_key):
    return PAGE_SCHEMAS.get(page_key, {'title': page_key, 'blocks': []})


def get_page_blocks(page_key):
    from apps.core.models import InstitutionalPage

    page = InstitutionalPage.objects.filter(page_key=page_key).first()
    return page.blocks if page and isinstance(page.blocks, dict) else {}
