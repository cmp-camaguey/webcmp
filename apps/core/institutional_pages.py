# ruff: noqa: E501
"""Fixed schemas for dashboard-editable institutional pages.

The template owns structure; the dashboard edits only these predefined blocks.
"""

import re

PAGE_SCHEMAS = {
    'vision': {
        'title': 'Visión',
        'blocks': [
            {
                'name': 'hero_description',
                'label': 'Descripción principal',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Somos el sistema integral rector de la actividad meteorológica en la provincia que mediante la aplicación de nuestra producción científica logra impactos positivos en la economía, la sociedad y el medio ambiente cubano.',
            },
            {
                'name': 'section_title',
                'label': 'Título de sección',
                'group': 'Sección principal',
                'type': 'char',
                'default': 'Valores que nos guían',
            },
            {
                'name': 'section_description',
                'label': 'Descripción de sección',
                'group': 'Sección principal',
                'type': 'textarea',
                'default': 'Los principios que orientan el trabajo de nuestros especialistas cada jornada.',
            },
            {
                'type': 'card_set',
                'name': 'cards',
                'group_label': 'Tarjeta',
                'item_label': 'Valor',
                'fields': [
                    {'suffix': 'title', 'label': 'Título', 'type': 'char'},
                    {'suffix': 'icon', 'label': 'Icono', 'type': 'icon'},
                    {'suffix': 'text', 'label': 'Texto', 'type': 'textarea'},
                ],
                'defaults': [
                    {
                        'title': 'Rigor científico',
                        'icon': 'ti-briefcase',
                        'text': 'Fundamentamos cada pronóstico y aviso en la observación sistemática y el análisis técnico de los fenómenos atmosféricos.',
                    },
                    {
                        'title': 'Servicio a la comunidad',
                        'icon': 'ti-users',
                        'text': 'Ponemos la información meteorológica al alcance de todos, con lenguaje claro y orientación oportuna para la toma de decisiones.',
                    },
                    {
                        'title': 'Trabajo en equipo',
                        'icon': 'ti-users-group',
                        'text': 'Integramos especialistas de la vigilancia, el pronóstico y la investigación para ofrecer un servicio único y consistente.',
                    },
                    {
                        'title': 'Compromiso social',
                        'icon': 'ti-heart',
                        'text': 'Velamos por reducir las pérdidas de bienes y proteger la vida ante desastres naturales de origen meteorológico.',
                    },
                ],
            },
        ],
    },
    'mission': {
        'title': 'Misión',
        'blocks': [
            {
                'name': 'hero_paragraph_1',
                'label': 'Descripción principal - Párrafo 1',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'El Centro Meteorológico es la institución encargada de suministrar información meteorológica y climática autorizada, confiable y oportuna sobre el estado y comportamiento futuro de la atmósfera.',
            },
            {
                'name': 'hero_paragraph_2',
                'label': 'Descripción principal - Párrafo 2',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Esta información está dirigida a velar por la seguridad de la vida humana y reducir las pérdidas de bienes materiales ante desastres naturales de origen meteorológico, contribuyendo directamente al bienestar de la comunidad y al desarrollo sostenible.',
            },
            {
                'name': 'section_title',
                'label': 'Título de sección',
                'group': 'Sección principal',
                'type': 'char',
                'default': 'Nuestros compromisos',
            },
            {
                'name': 'section_description',
                'label': 'Descripción de sección',
                'group': 'Sección principal',
                'type': 'textarea',
                'default': 'La razón de ser de nuestra labor de vigilancia meteorológica.',
            },
            {
                'type': 'card_set',
                'name': 'cards',
                'group_label': 'Tarjeta',
                'item_label': 'Compromiso',
                'fields': [
                    {'suffix': 'title', 'label': 'Título', 'type': 'char'},
                    {'suffix': 'icon', 'label': 'Icono', 'type': 'icon'},
                    {'suffix': 'text', 'label': 'Texto', 'type': 'textarea'},
                ],
                'defaults': [
                    {
                        'title': 'Proteger la vida',
                        'icon': 'ti-shield-check',
                        'text': 'Dirigimos la información a velar por la seguridad de la vida humana y a reducir las pérdidas de bienes materiales ante desastres naturales de origen meteorológico.',
                    },
                    {
                        'title': 'Vigilancia permanente',
                        'icon': 'ti-clock-24',
                        'text': 'Mantenemos la observación y el seguimiento de los fenómenos atmosféricos durante las 24 horas, todos los días del año.',
                    },
                    {
                        'title': 'Información oportuna',
                        'icon': 'ti-bell',
                        'text': 'Emisión de avisos y alertas con la antelación necesaria para que la población y los organismos tomen decisiones seguras.',
                    },
                    {
                        'title': 'Desarrollo sostenible',
                        'icon': 'ti-leaf',
                        'text': 'Contribuimos directamente al bienestar de la comunidad y al desarrollo sostenible de la provincia de Camagüey.',
                    },
                ],
            },
        ],
    },
    'about': {
        'title': 'Quiénes somos',
        'blocks': [
            {
                'name': 'hero_paragraph_1',
                'label': 'Descripción principal - Párrafo 1',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'El Centro Meteorológico Provincial de Camagüey integra el sistema del Instituto de Meteorología de Cuba (INSMET) y presta servicios meteorológicos autorizados a la población y a las entidades de la provincia.',
            },
            {
                'name': 'hero_paragraph_2',
                'label': 'Descripción principal - Párrafo 2',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Nuestra institución vigila el estado de la atmósfera sobre los 13 municipios de la provincia, elabora los pronósticos del tiempo, emite avisos ante fenómenos meteorológicos peligrosos y desarrolla investigaciones que contribuyen al conocimiento del clima de la región.',
            },
            {
                'name': 'section_title',
                'label': 'Título de sección',
                'group': 'Sección principal',
                'type': 'char',
                'default': 'El quehacer del Centro',
            },
            {
                'name': 'section_description',
                'label': 'Descripción de sección',
                'group': 'Sección principal',
                'type': 'textarea',
                'default': 'Vigilancia, investigación, servicios y contacto directo con la comunidad.',
            },
            {
                'type': 'card_set',
                'name': 'cards',
                'group_label': 'Tarjeta',
                'item_label': 'Tarjeta',
                'fields': [
                    {'suffix': 'title', 'label': 'Título', 'type': 'char'},
                    {'suffix': 'icon', 'label': 'Icono', 'type': 'icon'},
                    {'suffix': 'text', 'label': 'Texto', 'type': 'textarea'},
                ],
                'defaults': [
                    {
                        'title': 'Investigación',
                        'icon': 'ti-book-2',
                        'text': 'Publicaciones científicas y resultados de la investigación meteorológica provincial.',
                    },
                    {
                        'title': 'Servicios',
                        'icon': 'ti-tools',
                        'text': 'Servicios públicos y comerciales de asesoría e información meteorológica en línea.',
                    },
                    {
                        'title': 'Información institucional',
                        'icon': 'ti-sitemap',
                        'text': 'Organización, directivos, funciones y estrategia de desarrollo del Centro.',
                    },
                ],
            },
        ],
    },
    'institutional_information': {
        'title': 'Información institucional',
        'blocks': [
            {
                'name': 'hero_description',
                'label': 'Descripción principal',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Información pública sobre la organización, dirección y estrategia de desarrollo del Centro Meteorológico Provincial de Camagüey.',
            },
            {
                'name': 'org_title',
                'label': 'Título',
                'group': 'Estructura organizativa',
                'type': 'char',
                'default': 'Estructura organizativa',
            },
            {
                'name': 'org_description',
                'label': 'Descripción',
                'group': 'Estructura organizativa',
                'type': 'textarea',
                'default': 'La estructura organizativa del Centro responde a las funciones de dirección, vigilancia meteorológica, pronósticos, servicios, investigación y apoyo técnico-administrativo, en correspondencia con el sistema del INSMET.',
            },
            {
                'name': 'org_body',
                'label': 'Contenido',
                'group': 'Estructura organizativa',
                'type': 'textarea',
                'default': '<ul><li><strong>Dirección:</strong> conducción estratégica, representación institucional y toma de decisiones.</li><li><strong>Grupo de Pronósticos:</strong> elaboración de pronósticos, avisos y vigilancias meteorológicas.</li><li><strong>Red de Estaciones:</strong> observación meteorológica y mantenimiento de la red provincial.</li><li><strong>Servicios Científico-Técnicos:</strong> servicios comerciales, asesoría y productos especializados.</li><li><strong>Apoyo administrativo y técnico:</strong> gestión administrativa, informática y aseguramiento operativo.</li></ul>',
            },
            {
                'name': 'directors_title',
                'label': 'Título',
                'group': 'Directivos',
                'type': 'char',
                'default': 'Directivos',
            },
            {
                'name': 'directors_description',
                'label': 'Descripción',
                'group': 'Directivos',
                'type': 'textarea',
                'default': 'Información de la dirección institucional según lo dispuesto en la Ley 168/2024. Para asuntos oficiales, utilice el correo institucional de contacto.',
            },
            {
                'type': 'row_set',
                'name': 'directors_rows',
                'group': 'Directivos',
                'group_label': 'Directivos',
                'fields': [
                    {'suffix': 'cargo', 'label': 'Cargo', 'type': 'char'},
                    {'suffix': 'funciones', 'label': 'Funciones principales', 'type': 'char'},
                    {'suffix': 'correo', 'label': 'Correo institucional', 'type': 'char'},
                ],
                'defaults': [
                    {
                        'cargo': 'Dirección del Centro',
                        'funciones': 'Dirección, representación y gestión institucional del Centro Meteorológico Provincial de Camagüey.',
                        'correo': 'direccion@cmw.insmet.cu',
                    },
                ],
            },
            {
                'name': 'strategy_title',
                'label': 'Título',
                'group': 'Estrategia de desarrollo',
                'type': 'char',
                'default': 'Estrategia de desarrollo',
            },
            {
                'name': 'strategy_body',
                'label': 'Contenido',
                'group': 'Estrategia de desarrollo',
                'type': 'textarea',
                'default': '<p>La estrategia de desarrollo del Centro se orienta a fortalecer la vigilancia meteorológica continua, modernizar los servicios de información y avisos a la población, elevar la calidad de los productos científicos y comerciales, y consolidar la transformación digital institucional para contribuir al desarrollo sostenible y la reducción de riesgos ante desastres meteorológicos en la provincia de Camagüey.</p>',
            },
        ],
    },
    'legal_notice': {
        'title': 'Aviso legal',
        'blocks': [
            {
                'name': 'hero_description',
                'label': 'Descripción principal',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Identidad y datos de contacto del titular del sitio web del Centro Meteorológico Provincial de Camagüey.',
            },
            {
                'name': 'card_title',
                'label': 'Título de la tarjeta',
                'group': 'Contenido del aviso',
                'type': 'char',
                'default': 'Titular del sitio web',
            },
            {
                'name': 'institutional_condition',
                'label': 'Condición institucional',
                'group': 'Contenido del aviso',
                'type': 'char',
                'default': 'Centro Meteorológico Provincial de Camagüey, organismo del Estado encargado de la información meteorológica y climática en la provincia.',
            },
            {
                'name': 'footer_note',
                'label': 'Nota final',
                'group': 'Contenido del aviso',
                'type': 'textarea',
                'default': 'Este aviso legal se publica en cumplimiento de la Resolución 58/2022, artículo 6.c, que exige identificar la titularidad del sitio web institucional.',
            },
        ],
    },
    'data_subject_rights': {
        'title': 'Derechos del titular',
        'blocks': [
            {
                'name': 'hero_description',
                'label': 'Descripción principal',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Canal para ejercer sus derechos de Acceso, Rectificación, Cancelación, Oposición y Portabilidad (ARCO/ARCOP) sobre sus datos personales según la Resolución 58/2022 y normativa cubana vigente.',
            },
            {
                'name': 'form_intro',
                'label': 'Introducción',
                'group': 'Formulario de solicitud',
                'type': 'textarea',
                'group_note': 'Los campos del formulario público son fijos y no se editan desde este panel.',
                'default': 'Complete el formulario para ejercer sus derechos. Las solicitudes las atiende el Delegado de Protección de Datos, también en el correo institucional de contacto. Recibirá un correo de confirmación y le notificaremos el resultado en un plazo máximo de 30 días hábiles.',
            },
            {
                'name': 'after_submit_title',
                'label': 'Título',
                'group': 'Qué pasa después de enviar',
                'type': 'char',
                'default': 'Qué pasa después de enviar',
            },
            {
                'name': 'after_submit_body',
                'label': 'Contenido',
                'group': 'Qué pasa después de enviar',
                'type': 'textarea',
                'default': 'Confirmación de recibo: Inmediata, por correo automático.\nRespuesta: Máximo 30 días hábiles desde la recepción de la solicitud.\nPrórroga: Hasta 30 días hábiles adicionales, notificándole la causa.\nIdentidad: Podremos solicitar un documento acreditativo si resulta necesario.',
            },
            {
                'name': 'rights_title',
                'label': 'Título',
                'group': 'Información sobre los derechos',
                'type': 'char',
                'default': 'Información sobre sus derechos',
            },
            {
                'name': 'rights_intro',
                'label': 'Introducción',
                'group': 'Información sobre los derechos',
                'type': 'char',
                'default': 'El ejercicio de estos derechos es gratuito.',
            },
            {
                'name': 'rights_body',
                'label': 'Contenido',
                'group': 'Información sobre los derechos',
                'type': 'textarea',
                'default': 'Acceso: Obtener confirmación de si se tratan sus datos y acceder a ellos.\nRectificación: Solicitar la corrección de datos inexactos o incompletos.\nCancelación: Solicitar la supresión de sus datos cuando ya no sean necesarios.\nOposición: Oponerse al tratamiento de sus datos para fines específicos.\nPortabilidad: Recibir sus datos en un formato estructurado y de uso común.',
            },
        ],
    },
    'cookie_policy': {
        'title': 'Política de cookies',
        'blocks': [
            {
                'name': 'hero_description',
                'label': 'Descripción principal',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Qué son las cookies, qué categorías usamos, para qué sirven y cómo gestionar tu consentimiento.',
            },
            {
                'name': 'section_que_son',
                'label': '1. ¿Qué son las cookies?',
                'group': '1. ¿Qué son las cookies?',
                'type': 'textarea',
                'default': 'Una cookie es un pequeño archivo de texto que un sitio web guarda en tu dispositivo cuando lo visitas. Permite que el sitio recuerde información sobre tu visita (por ejemplo, que hayas iniciado sesión o que ya hayas visto el banner de consentimiento).\n\nEsta Política explica qué cookies usa este sitio, para qué sirve cada una y cómo puedes gestionar tu consentimiento. Complementa el [Aviso de Privacidad](/institucion/politica-privacidad/).',
            },
            {
                'name': 'section_categorias',
                'label': '2. Categorías de cookies que usamos',
                'group': '2. Categorías de cookies que usamos',
                'type': 'textarea',
                'default': '<p><strong>Necesarias (siempre activas)</strong></p><p>Esenciales para que el sitio funcione: mantener tu sesión autenticada, proteger formularios contra ataques CSRF y recordar tu elección de consentimiento. En el panel interno también se usa el estado de la barra lateral. <strong>No requieren consentimiento</strong>, porque sin ellas el sitio no puede prestar el servicio.</p><p><strong>Analítica / Rendimiento (requieren consentimiento)</strong></p><p>Usamos <strong>RUM (Real User Monitoring)</strong> para medir el rendimiento real que experimentan los visitantes: tiempos de carga (LCP, FCP), interactividad (INP), estabilidad visual (CLS), peso de recursos transferidos, y errores de JavaScript. Los datos se agregan y anonimizan (IP truncada, sin identificadores personales) y sirven exclusivamente para mejorar la calidad y disponibilidad del servicio. <strong>Solo se activan si das tu consentimiento</strong>.</p><p><strong>Funcionales (requieren consentimiento, futuras)</strong></p><p>Reservadas para futuras mejoras: recordar preferencias de visualización (tema, idioma), mapas interactivos, contenidos incrustados de terceros. Actualmente no hay cookies funcionales activas.</p>',
            },
            {
                'type': 'row_set',
                'name': 'cookie_rows',
                'group': '3. Detalle de cookies utilizadas',
                'table_layout': 'auto',
                'fields': [
                    {'suffix': 'nombre', 'label': 'Nombre', 'type': 'char'},
                    {'suffix': 'categoria', 'label': 'Categoría', 'type': 'char'},
                    {'suffix': 'duracion', 'label': 'Duración', 'type': 'char'},
                    {'suffix': 'descripcion', 'label': 'Descripción', 'type': 'char'},
                ],
                'defaults': [
                    {
                        'nombre': 'sessionid',
                        'categoria': 'Necesaria',
                        'duracion': 'Sesión',
                        'descripcion': 'Identificador de sesión de Django (usuario autenticado en panel).',
                    },
                    {
                        'nombre': 'csrftoken',
                        'categoria': 'Necesaria',
                        'duracion': '1 año',
                        'descripcion': 'Protección CSRF de formularios.',
                    },
                    {
                        'nombre': 'cookie_consent',
                        'categoria': 'Necesaria',
                        'duracion': '1 año',
                        'descripcion': 'Guarda tu elección de consentimiento (aceptar/rechazar/configurar).',
                    },
                    {
                        'nombre': 'rum_session',
                        'categoria': 'Analítica',
                        'duracion': '30 min (inactividad)',
                        'descripcion': 'ID de sesión anónima para agrupar métricas RUM (solo si consientes analítica).',
                    },
                ],
            },
            {
                'name': 'section_consentimiento',
                'label': '4. Cómo gestionar tu consentimiento',
                'group': '4. Cómo gestionar tu consentimiento',
                'type': 'textarea',
                'default': '<p>Al visitar el sitio por primera vez, verás un <strong>banner de consentimiento</strong> en la parte inferior con tres opciones:</p><ul><li><strong>Aceptar todo</strong>: habilita analítica y funcionales.</li><li><strong>Rechazar analítica</strong>: solo necesarias (RUM desactivado).</li><li><strong>Configurar</strong>: elige categoría por categoría en el modal.</li></ul><p>Tu preferencia se guarda en la cookie <code>cookie_consent</code> (y en <code>localStorage</code> como respaldo) durante <strong>1 año</strong>. Puedes cambiarla en cualquier momento desde el enlace <strong>«Configurar cookies»</strong> en el pie de página, que vuelve a abrir el modal.</p>',
            },
            {
                'name': 'section_desactivar',
                'label': '5. Cómo desactivar o borrar cookies desde el navegador',
                'group': '5. Cómo desactivar o borrar cookies desde el navegador',
                'type': 'textarea',
                'default': 'Además del control interno, puedes bloquear o eliminar cookies desde la configuración de tu navegador: [Chrome](https://support.google.com/chrome/answer/95647), [Firefox](https://support.mozilla.org/es/kb/habilitar-y-deshabilitar-cookies), [Safari](https://support.apple.com/es-es/guide/safari/sfri11471/mac) o [Edge](https://support.microsoft.com/es-es/microsoft-edge/eliminar-cookies-en-microsoft-edge-63947406-40ac-c3b8-57b9-2a946a29ae09).\n\nTen en cuenta que bloquear las cookies necesarias impedirá que el panel de administración funcione correctamente.',
            },
            {
                'name': 'section_contacto',
                'label': '6. Responsable y contacto',
                'group': '6. Responsable y contacto',
                'type': 'textarea',
                'default': 'Titular: [nombre de la entidad]\nContacto: [correo institucional] · [Ver aviso legal](/institucion/aviso-legal/)',
            },
            {
                'name': 'section_actualizaciones',
                'label': '7. Actualizaciones',
                'group': '7. Actualizaciones',
                'type': 'textarea',
                'default': '<p>Esta política se revisa periódicamente. La versión vigente siempre está accesible en esta misma URL. Los cambios sustanciales se comunican por el boletín y en el panel de administración.</p>',
            },
            {
                'type': 'section_set',
                'name': 'extra_sections',
                'group_label': 'Punto adicional',
                'fields': [
                    {'suffix': 'title', 'label': 'Título', 'type': 'char'},
                    {'suffix': 'content', 'label': 'Contenido', 'type': 'textarea'},
                ],
                'defaults': [],
            },
        ],
    },
    'privacy_policy': {
        'title': 'Política de privacidad',
        'blocks': [
            {
                'name': 'hero_description',
                'label': 'Descripción principal',
                'group': 'Encabezado de página',
                'type': 'textarea',
                'default': 'Cómo tratamos tus datos personales, con qué finalidad, durante cuánto tiempo y cómo puedes ejercer tus derechos.',
            },
            {
                'name': 'section_responsable',
                'label': '1. Responsable del tratamiento',
                'group': '1. Responsable del tratamiento',
                'type': 'textarea',
                'default': '<p><strong>Titular:</strong> [nombre de la entidad]</p><p><strong>Contacto:</strong> [correo institucional] · Ver aviso legal</p>',
            },
            {
                'name': 'section_datos',
                'label': '2. Datos que tratamos y finalidad',
                'group': '2. Datos que tratamos y finalidad',
                'type': 'textarea',
                'default': '<p>El portal trata las siguientes categorías de datos personales:</p><ul><li><strong>Suscriptores al boletín informativo:</strong> correo electrónico, origen de la suscripción, fecha de confirmación y estado de la suscripción. Finalidad: envío de avisos meteorológicos, noticias y novedades del Centro.</li><li><strong>Usuarios del panel de administración:</strong> nombre de usuario, correo, nombre y apellidos, avatar opcional, condición de usuario LDAP, preferencia de boletín. Finalidad: autenticación, autorización, gestión de contenidos, notificaciones internas.</li><li><strong>Clientes comerciales:</strong> datos fiscales (REEUP, NIT, cuenta bancaria, agencia, registro comercial, dirección, teléfonos), tipo de cliente, representante legal. Finalidad: facturación, gestión de contratos, emisión de certificados, servicios contratados.</li><li><strong>Facturación y pagos:</strong> datos de facturas, asignaciones de coste, cobros. Finalidad: cumplimiento de obligaciones tributarias y contables.</li><li><strong>Log de acceso y métricas técnicas (RUM):</strong> dirección IP anonimizada, user-agent, ruta solicitada, tiempo de respuesta, errores HTTP. Finalidad: monitorización de disponibilidad, rendimiento y seguridad del servicio.</li></ul>',
            },
            {
                'name': 'section_destinatarios',
                'label': '3. Destinatarios',
                'group': '3. Destinatarios',
                'type': 'textarea',
                'default': '<p>Los datos no se ceden a terceros salvo obligación legal o cuando sea necesario para la prestación del servicio contratado:</p><ul><li>Entidades bancarias para la gestión de cobros y pagos.</li><li>Administración tributaria (ONAT) en cumplimiento de obligaciones fiscales.</li><li>Proveedores de infraestructura (alojamiento, correo) bajo cláusulas de encargado de tratamiento.</li></ul>',
            },
            {
                'name': 'section_transferencias',
                'label': '4. Transferencias internacionales',
                'group': '4. Transferencias internacionales',
                'type': 'textarea',
                'default': '<p>No se realizan transferencias internacionales de datos personales. Todo el tratamiento se realiza en infraestructura nacional (Cuba).</p>',
            },
            {
                'name': 'section_conservacion',
                'label': '5. Plazos de conservación',
                'group': '5. Plazos de conservación',
                'type': 'textarea',
                'default': '<ul><li>Suscriptores: mientras la suscripción esté activa; tras la baja se conserva el correo y la prueba de consentimiento durante 4 años para acreditar el cumplimiento.</li><li>Usuarios del panel: mientras la cuenta exista; tras la baja se anonimizan los datos de perfil en 30 días.</li><li>Clientes y facturación: 10 años desde la finalización de la relación contractual, por obligación contable y tributaria.</li><li>Logs técnicos y métricas: 12 meses en bruto; agregados estadísticos sin datos personales se conservan indefinidamente.</li></ul>',
            },
            {
                'name': 'section_derechos',
                'label': '6. Derechos del titular',
                'group': '6. Derechos del titular',
                'type': 'textarea',
                'default': '<p>Tienes derecho a:</p><ul><li>Acceder a tus datos personales.</li><li>Rectificar datos inexactos o incompletos.</li><li>Suprimir tus datos cuando ya no sean necesarios.</li><li>Limitar el tratamiento.</li><li>Oponerte al tratamiento (incluye marketing directo).</li><li>Portabilidad de los datos que nos hayas facilitado.</li><li>Retirar el consentimiento en cualquier momento (para tratamientos basados en consentimiento).</li></ul><p>Para ejercer tus derechos, envía una solicitud al correo institucional indicando el derecho que ejercitas y adjuntando copia de tu documento de identidad.</p>',
            },
            {
                'name': 'section_seguridad',
                'label': '7. Medidas de seguridad',
                'group': '7. Medidas de seguridad',
                'type': 'textarea',
                'default': '<p>Se aplican medidas técnicas y organizativas adecuadas al riesgo: acceso por autenticación fuerte, control de accesos por roles, registro de accesos, cifrado en tránsito (TLS), copias de seguridad cifradas y procedimiento de notificación de incidentes.</p>',
            },
            {
                'name': 'section_actualizaciones',
                'label': '8. Actualizaciones',
                'group': '8. Actualizaciones',
                'type': 'textarea',
                'default': '<p>Esta política se revisa periódicamente. La versión vigente siempre está accesible en esta misma URL. Los cambios sustanciales se comunican por el boletín y en el panel de administración.</p>',
            },
            {
                'type': 'section_set',
                'name': 'extra_sections',
                'group_label': 'Punto adicional',
                'fields': [
                    {'suffix': 'title', 'label': 'Título', 'type': 'char'},
                    {'suffix': 'content', 'label': 'Contenido', 'type': 'textarea'},
                ],
                'defaults': [],
            },
        ],
    },
}


def get_page_schema(page_key):
    return PAGE_SCHEMAS.get(page_key, {'title': page_key, 'blocks': []})


def expand_schema_blocks(schema_blocks, blocks_data=None):
    """Expand card_set definitions into concrete field blocks."""
    data = blocks_data or {}
    expanded = []
    for block in schema_blocks:
        if block.get('type') == 'card_set':
            defaults = block.get('defaults', [])
            fields = block.get('fields', [])
            group_label = block.get('group_label', 'Tarjeta')
            max_n = len(defaults)
            for key in data:
                m = re.match(r'^card_(\d+)_', key)
                if m:
                    max_n = max(max_n, int(m.group(1)))
            for i in range(1, max_n + 1):
                default_item = defaults[i - 1] if i - 1 < len(defaults) else {}
                for field in fields:
                    suffix = field['suffix']
                    name = f'card_{i}_{suffix}'
                    expanded.append(
                        {
                            'name': name,
                            'label': field['label'],
                            'group': f'{group_label} {i}',
                            'type': field['type'],
                            'default': default_item.get(suffix, ''),
                            'card_index': i,
                            'card_set': block.get('name', 'cards'),
                        }
                    )
            continue

        if block.get('type') == 'row_set':
            defaults = block.get('defaults', [])
            fields = block.get('fields', [])
            group = block.get('group', block.get('group_label', 'Filas'))
            max_n = len(defaults)
            prefix = block.get('name', 'rows')
            for key in data:
                m = re.match(rf'^{re.escape(prefix)}_(\d+)_', key)
                if m:
                    max_n = max(max_n, int(m.group(1)))
            for i in range(1, max_n + 1):
                default_item = defaults[i - 1] if i - 1 < len(defaults) else {}
                for field in fields:
                    suffix = field['suffix']
                    name = f'{prefix}_{i}_{suffix}'
                    expanded.append(
                        {
                            'name': name,
                            'label': field['label'],
                            'group': group,
                            'type': field['type'],
                            'default': default_item.get(suffix, ''),
                            'row_index': i,
                            'row_set': prefix,
                            'row_field': suffix,
                        }
                    )
            continue

        if block.get('type') == 'section_set':
            defaults = block.get('defaults', [])
            fields = block.get('fields', [])
            group_label = block.get('group_label', 'Sección')
            prefix = block.get('name', 'sections')
            max_n = len(defaults)
            for key in data:
                m = re.match(rf'^{re.escape(prefix)}_(\d+)_', key)
                if m:
                    max_n = max(max_n, int(m.group(1)))
            for i in range(1, max_n + 1):
                default_item = defaults[i - 1] if i - 1 < len(defaults) else {}
                for field in fields:
                    suffix = field['suffix']
                    name = f'{prefix}_{i}_{suffix}'
                    expanded.append(
                        {
                            'name': name,
                            'label': field['label'],
                            'group': f'{group_label} {i}',
                            'type': field['type'],
                            'default': default_item.get(suffix, ''),
                            'section_index': i,
                            'section_set': prefix,
                        }
                    )
            continue

        expanded.append(block)
    return expanded


def get_page_blocks(page_key):
    from apps.core.models import InstitutionalPage

    page = InstitutionalPage.objects.filter(page_key=page_key).first()
    return page.blocks if page and isinstance(page.blocks, dict) else {}


def get_card_items(blocks_data, defaults=None):
    """Return card items as list of dicts for template rendering."""
    data = blocks_data or {}
    defaults = defaults or []
    max_n = len(defaults)
    for key in data:
        m = re.match(r'^card_(\d+)_', key)
        if m:
            max_n = max(max_n, int(m.group(1)))
    items = []
    for i in range(1, max_n + 1):
        default_item = defaults[i - 1] if i - 1 < len(defaults) else {}
        item = {'index': i}
        for suffix in ('title', 'icon', 'text'):
            val = data.get(f'card_{i}_{suffix}', '')
            item[suffix] = val if val else default_item.get(suffix, '')
        has_data = any(f'card_{i}_{s}' in data for s in ('title', 'icon', 'text'))
        if has_data or i <= len(defaults):
            items.append(item)
    return items


def get_page_cards(page_key):
    """Return card items for a page, using schema defaults."""
    schema = get_page_schema(page_key)
    defaults = []
    for block in schema.get('blocks', []):
        if block.get('type') == 'card_set':
            defaults = block.get('defaults', [])
            break
    return get_card_items(get_page_blocks(page_key), defaults)


def get_row_items(blocks_data, prefix, defaults=None, fields=None):
    """Return row_set items as list of dicts for template rendering."""
    data = blocks_data or {}
    defaults = defaults or []
    suffixes = [f['suffix'] for f in (fields or [])] or ['cargo', 'funciones', 'correo']
    max_n = len(defaults)
    pattern = re.compile(rf'^{re.escape(prefix)}_(\d+)_')
    for key in data:
        m = pattern.match(key)
        if m:
            max_n = max(max_n, int(m.group(1)))
    items = []
    for i in range(1, max_n + 1):
        default_item = defaults[i - 1] if i - 1 < len(defaults) else {}
        item = {'index': i}
        for suffix in suffixes:
            val = data.get(f'{prefix}_{i}_{suffix}', '')
            item[suffix] = val if val else default_item.get(suffix, '')
        has_data = any(f'{prefix}_{i}_{s}' in data for s in suffixes)
        if has_data or i <= len(defaults):
            items.append(item)
    return items


def get_page_row_sets(page_key):
    """Return dict of row_set name -> items for a page."""
    schema = get_page_schema(page_key)
    blocks_data = get_page_blocks(page_key)
    result = {}
    for block in schema.get('blocks', []):
        if block.get('type') == 'row_set':
            name = block.get('name', 'rows')
            result[name] = get_row_items(
                blocks_data,
                name,
                block.get('defaults', []),
                block.get('fields', []),
            )
    return result
