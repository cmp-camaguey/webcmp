import re

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import SiteConfiguration
from apps.monitoring.models import RequestMetric


def superuser(username='root'):
    return User.objects.create_superuser(
        username, f'{username}@example.com', 'pass', first_name='Root', last_name='User'
    )


class SiteMonitoringAccessTests(TestCase):
    def setUp(self):
        SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})

    def test_anonimo_va_al_login(self):
        response = self.client.get(reverse('dashboard:monitoring'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/', response['Location'])

    def test_staff_sin_superusuario_no_entra(self):
        # El perfil completo evita el redirect de `CheckUserProfileMiddleware`:
        # lo que se prueba es el rechazo de la vista, no el middleware de perfil.
        user = User.objects.create_user(
            'staff',
            'staff@example.com',
            'pass',
            first_name='Staff',
            last_name='User',
            is_staff=True,
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('dashboard:monitoring')).status_code, 403)
        self.assertEqual(self.client.get(reverse('dashboard:monitoring_data')).status_code, 403)

    def test_superusuario_ve_el_panel(self):
        self.client.force_login(superuser())
        response = self.client.get(reverse('dashboard:monitoring'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['title'], 'Monitoreo del sitio')
        self.assertEqual(response.context['segment'], 'site_monitoring')
        self.assertIn('snapshot', response.context)
        self.assertContains(response, 'Recursos del servidor')
        self.assertContains(response, 'Métricas web esenciales')
        self.assertContains(response, 'Tráfico en vivo')

    def test_endpoint_json_trae_el_snapshot_completo(self):
        self.client.force_login(superuser())
        response = self.client.get(reverse('dashboard:monitoring_data'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in (
            'generated_at',
            'enabled',
            'status',
            'system',
            'health',
            'http',
            'uptime',
            'incident',
            'traffic',
            'vitals',
            'errors',
            'weight',
        ):
            self.assertIn(key, data)
        self.assertIn('cpu', data['system'])
        self.assertIn('slots', data['uptime'])
        self.assertEqual(len(data['uptime']['slots']), 48)

    @override_settings(MONITORING_ENABLED=True)
    def test_sin_captura_no_se_muestra_el_aviso_de_apagado(self):
        self.client.force_login(superuser())
        response = self.client.get(reverse('dashboard:monitoring'))
        self.assertNotContains(response, 'MONITORING_ENABLED=False')

    def test_con_captura_apagada_se_avisa(self):
        self.client.force_login(superuser())
        response = self.client.get(reverse('dashboard:monitoring'))
        self.assertContains(response, 'MONITORING_ENABLED=False')


class MonitoringPanelLayoutTests(TestCase):
    """El rediseño conserva el contrato vivo del panel y es usable en móvil."""

    def setUp(self):
        SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})
        self.client.force_login(superuser())
        self.html = self.client.get(reverse('dashboard:monitoring')).content.decode()
        base = settings.BASE_DIR
        self.js = (base / 'static/dist/js/site-monitoring.js').read_text()
        self.template = (
            base / 'apps/dashboard/templates/pages/dashboard/monitoring.html'
        ).read_text()

    def test_la_consola_de_estado_expone_los_hooks_del_refresco(self):
        # El JS busca estos nodos para pausar, refrescar y teñir el estado.
        # Si el rediseño los pierde, el panel deja de actualizarse en vivo.
        for marker in (
            'id="monitoringRoot"',
            'data-status-label',
            'data-status-badge',
            'id="monitoringToggle"',
            'id="monitoringRefresh"',
            'data-uptime-slots',
            'data-cores',
            'data-vital-metric=',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)

    def test_todas_las_tablas_tienen_desbordamiento_horizontal(self):
        # En una pantalla estrecha las columnas de errores y rutas deben
        # desplazarse dentro de la tarjeta, no romper el ancho de la página.
        for name in ('top_pages', 'referrers', 'devices', 'browsers', 'errors'):
            with self.subTest(table=name):
                self.assertRegex(
                    self.html,
                    rf'class="table-responsive[^"]*">\s*<table[^>]*>\s*'
                    rf'(?:<thead>[\s\S]*?</thead>\s*)?<tbody data-table="{name}"',
                )

    def test_los_iconos_decorativos_son_invisibles_para_lectores_de_pantalla(self):
        # Un icono al lado de una etiqueta no aporta información: anunciarlo
        # duplica el contenido para quien navega con lector de pantalla.
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        iconos = re.findall(r'<i\s+class="icon[^>]*>', panel)
        self.assertTrue(iconos)
        for icono in iconos:
            with self.subTest(icono=icono):
                self.assertIn('aria-hidden="true"', icono)

    def test_los_encabezados_de_tabla_llevan_scope(self):
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        for th in re.findall(r'<th\b[^>]*>', panel):
            with self.subTest(th=th):
                self.assertIn('scope="col"', th)

    def test_un_solo_sistema_de_espacios_con_tabla_y_paginador_juntos(self):
        # Tres alturas mínimas distintas dejaban un hueco muerto abajo: el
        # contenido colgaba arriba y el paginador se separaba de su tabla.
        # Ahora una sola clase reparte el contenido con flex y la tabla crece
        # hasta su paginador.
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        cards = re.findall(r'<div class="card ([^"]*)"', panel)
        de_fila = [clase for clase in cards if 'monitoring-card' in clase]
        self.assertEqual(len(de_fila), 10)
        for clase in de_fila:
            self.assertIn('h-100', clase)
        for vieja in ('monitoring-kpi-card', 'monitoring-half-card', 'monitoring-compact-card'):
            with self.subTest(clase=vieja):
                self.assertNotIn(vieja, self.html)

        self.assertIn('.monitoring-card > .card-body', self.html)
        self.assertIn('flex-direction: column', self.html)
        self.assertNotIn('min-height: 28rem', self.html)
        self.assertEqual(self.html.count('class="table-responsive monitoring-table-grow"'), 3)

        for name in ('top_pages', 'referrers', 'errors'):
            with self.subTest(tabla=name):
                self.assertRegex(
                    panel,
                    rf'table-responsive monitoring-table-grow">\s*<table[^>]*>\s*'
                    rf'(?:<thead>[\s\S]*?</thead>\s*)?<tbody data-table="{name}"',
                )
                # El paginador sigue justo después de su tabla: es la tabla
                # quien crece y lo empuja al fondo, no un margen que lo aparte.
                self.assertRegex(
                    panel,
                    rf'</tbody>\s*</table>\s*</div>\s*'
                    rf'<div class="d-flex align-items-center justify-content-end '
                    rf'gap-2 mt-2 invisible"\s*\s*data-paginator-for="{name}"',
                )

    def test_los_textos_del_panel_estan_en_espanol(self):
        # Los tecnicismos (CPU, RSS, Swap, Worker, p95, LCP, 5xx) se quedan:
        # son nombres de protocolo, acrónimos o el proceso real de Huey. Lo que
        # sí se lee como frase va en español, incluidos los valores que el
        # refresco escribe desde el snapshot.
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        for viejo in (
            'Core Web Vitals',
            'uptime del host',
            'Worker de tareas',
            'Intercambio',
            'Trabajador de tareas',
        ):
            with self.subTest(viejo=viejo):
                self.assertNotIn(viejo, panel)

        for nuevo in (
            'Métricas web esenciales',
            'tiempo de actividad del servidor',
            'Worker (PID',
            'Tareas (Huey)',
            '<span>Swap</span>',
        ):
            with self.subTest(nuevo=nuevo):
                self.assertIn(nuevo, panel)

        # El badge conserva el nivel corto: al lado ya dice "Operativo" y
        # repetir la etiqueta larga en la badge no aporta información.
        self.assertIn('data-status-badge>{{ snapshot.status.level }}', self.template)
        self.assertIn('badge.textContent = status.level || EMPTY', self.js)
        self.assertIn("badge.textContent = metric.rating_label || 'sin datos'", self.js)

    def test_rotulos_adaptativos_y_cifras_de_trafico_alineadas(self):
        # En pantallas anchas se conserva el rótulo completo; en móvil se
        # cambia por uno corto con CSS, sin tocar el HTML ni el refresco.
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        for largo, corto in (
            ('Peticiones simultáneas', 'Peticiones'),
            ('Peticiones por minuto', 'peticiones/min'),
            ('Recursos del servidor', 'Recursos'),
            ('tiempo de actividad del servidor', 'tiempo de actividad'),
            ('p75 de las últimas', 'p75 últimas'),
        ):
            with self.subTest(largo=largo):
                self.assertIn(largo, self.template)
                self.assertIn(corto, self.template)
        self.assertRegex(self.template, r'\.monitoring-short\s*\{\s*display:\s*none;')
        self.assertRegex(
            self.template,
            r'@media \(max-width: 575px\)\s*\{[^}]*?\.monitoring-long\s*\{'
            r'\s*display:\s*none;\s*\}\s*\.monitoring-short\s*\{\s*display:\s*inline',
        )
        self.assertIn('aria-label="Peticiones por minuto en los últimos 30 minutos"', panel)
        # La "h" de "últimas 24 h" no debe caer a otra línea en móvil.
        self.assertRegex(
            panel,
            r'<div class="ms-auto text-secondary small text-nowrap">\s*'
            r'<span class="monitoring-long">p75 de las últimas',
        )

        # La badge y los contadores de Huey viajan juntos: el bloque no se
        # parte a mitad de frase aunque la columna se angoste.
        self.assertRegex(
            panel,
            r'<div class="datagrid-content d-flex flex-wrap align-items-center gap-1">\s*'
            r'<span class="badge[^>]*?data-state-badge="health\.queue\.ok">',
        )
        self.assertIn('class="text-secondary small text-nowrap"', panel)

        # "Última captura" y su hora comparten línea aunque el bloque se
        # baje a una fila propia cuando el ancho no alcanza.
        self.assertRegex(
            panel,
            r'<div class="[^"]*d-flex align-items-baseline gap-2">\s*'
            r'<div class="monitoring-eyebrow">Última captura</div>\s*'
            r'<div class="small monitoring-figure"',
        )

        self.assertIn('row g-3 mb-3 monitoring-traffic-kpis', panel)
        self.assertRegex(
            self.template,
            r'\.monitoring-traffic-kpis\s*>\s*\[class\*="col-"\]\s*\{[^}]*?'
            r'display:\s*flex;\s*flex-direction:\s*column',
        )
        self.assertRegex(
            self.template,
            r'\.monitoring-traffic-kpis\s*\.monitoring-figure\s*\{[^}]*?margin-top:\s*auto',
        )

    def test_cabecera_hora_leyenda_y_cola_se_ordenen_en_movil(self):
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        # El título ocupa su propia fila en móvil: los botones no deben
        # comprimir "Monitoreo del sitio" hasta partirlo en dos líneas.
        # La cabecera se renderiza fuera de monitoringRoot.
        self.assertRegex(
            self.html,
            r'<div class="row g-2 align-items-center">\s*'
            r'<div class="col-12 col-md">\s*'
            r'<div class="page-pretitle">',
        )
        self.assertIn('<div class="col-12 col-md-auto d-flex justify-content-end">', self.html)

        # La hora se va a la derecha cuando el bloque baja de fila.
        self.assertRegex(
            panel,
            r'<div class="monitoring-last-capture[^"]*">\s*'
            r'<div class="monitoring-eyebrow">Última captura</div>',
        )
        self.assertRegex(
            self.template,
            r'\.monitoring-last-capture\s*\{[^}]*?'
            r'width:\s*100%;[^}]*?justify-content:\s*space-between',
        )

        # "Al día" y los contadores caben juntos si la celda ocupa las dos
        # columnas del datagrid; en anchos mayores vuelve a ser media celda.
        self.assertRegex(
            panel,
            r'<div class="datagrid-item monitoring-queue-wide">\s*'
            r'<div class="datagrid-title">Tareas \(Huey\)</div>',
        )
        self.assertRegex(
            self.template,
            r'@media \(max-width: 575px\)\s*\{[^}]*?\.monitoring-queue-wide\s*\{'
            r'\s*grid-column:\s*1\s*/\s*-1',
        )

        # La leyenda va en columnas fijas: con flex-wrap los círculos de la
        # segunda fila no alinean con los de la primera.
        self.assertIn('small monitoring-uptime-legend', panel)
        self.assertRegex(
            self.template,
            r'\.monitoring-uptime-legend\s*\{[^}]*?'
            r'display:\s*grid;[^}]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)',
        )

    def test_el_card_de_recursos_reparte_el_espacio_sobrante(self):
        # Recursos es hermano del card que lleva el chart HTTP (150px). Con
        # h-100 en los dos, Bootstrap estiraba al corto y el margin-top: auto
        # concentraba la diferencia en un hueco sobre el datagrid final. El
        # sobrante debe repartirse entre las dos secciones, sin agujero.
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        self.assertRegex(
            panel,
            r'<div class="card monitoring-card h-100">\s*'
            r'<div class="card-body monitoring-resources-body">\s*'
            r'<div class="d-flex align-items-center mb-3">\s*'
            r'<div class="monitoring-eyebrow">[\s\S]{0,200}?Recursos del servidor',
        )
        self.assertEqual(panel.count('card-body monitoring-resources-body'), 1)
        self.assertRegex(
            self.html,
            r'\.monitoring-card > \.card-body\.monitoring-resources-body > '
            r':last-child:not\(\.monitoring-chart\)\s*\{\s*margin-top:\s*0',
        )
        self.assertRegex(
            self.html,
            r'\.monitoring-card > \.card-body\.monitoring-resources-body > '
            r'\.row\.g-3,[\s\S]*?\.datagrid\.monitoring-pairs\s*\{[^}]*?'
            r'flex:\s*1 1 auto;[^}]*?align-content:\s*space-around',
        )
        # La regla general sigue empujando al fondo el último bloque del resto
        # de cards, incluidas las tablas con su paginador.
        self.assertIn(
            '.monitoring-card > .card-body > :last-child:not(.monitoring-chart)',
            self.html,
        )

    def test_los_tres_datagrids_muestran_sus_pares_en_dos_columnas(self):
        # `.datagrid` de Tabler usa minmax(15rem, 1fr): con el card angosto
        # (col-lg-6) todo cae a una columna aunque la ventana sea ancha. Un
        # @media por viewport no alcanza, y `extrastyle` se carga antes que el
        # CSS de Tabler: hace falta un selector de dos clases para ganar.
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        pares = re.findall(
            r'<div class="(datagrid[^"]*)">\s*'
            r'<div class="datagrid-item">\s*'
            r'<div class="datagrid-title">([^<]+)</div>',
            panel,
        )
        self.assertEqual(
            [titulo for _, titulo in pares],
            ['Red recibida', 'Base de datos', 'Tasa de error 5xx'],
        )
        for clase, titulo in pares:
            with self.subTest(datagrid=titulo):
                self.assertIn('monitoring-pairs', clase)
        self.assertRegex(
            self.html,
            r'\.datagrid\.monitoring-pairs\s*\{[^}]*?'
            r'grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)',
        )
        self.assertNotIn('@media (max-width: 575.98px)', self.html)

    def test_dispositivos_y_navegadores_muestran_barras_de_distribucion(self):
        # Dos tablas de número suelto se leen como listas. La barra reutiliza
        # el total de pageviews que ya viaja en el snapshot, sin consultas
        # nuevas, y el refresco debe reconstruirla con su propio renderer.
        for name in ('devices', 'browsers'):
            with self.subTest(tabla=name):
                bloque = self.template.split(f'<tbody data-table="{name}">', 1)[1]
                bloque = bloque.split('</tbody>', 1)[0]
                self.assertIn('monitoring-share-bar', bloque)
                self.assertIn('percent_of:snapshot.traffic.pageviews_30m', bloque)

        self.assertIn('function renderShareRows', self.js)
        for name in ('devices', 'browsers'):
            with self.subTest(render=name):
                self.assertIn(f'data-table="{name}"', self.js)
        self.assertNotIn('devices: (traffic.devices', self.js)
        self.assertNotIn('browsers: (traffic.browsers', self.js)

    def test_latencia_del_chart_http_se_dibuja_y_se_refresca(self):
        # `requests_per_minute` ya serializa avg_ms por minuto y el JS lo
        # descartaba. La serie nueva necesita eje propio y sobrevivir al
        # refresco; el chart de tráfico se queda con una sola serie.
        self.assertIn('function chartLatency', self.js)
        self.assertIn('point.avg_ms', self.js)
        self.assertIn('opposite: true', self.js)
        self.assertIn("'Latencia media'", self.js)
        self.assertIn("labels: { colors: 'var(--tblr-body-color)' }", self.js)
        # `--tblr-secondary` es gris fijo en ambos temas: con el fondo oscuro
        # la leyenda queda ilegible. `--tblr-body-color` usa light-dark().
        self.assertEqual(self.js.count('var(--tblr-body-color)'), 3)
        self.assertIn("updateChart('http', snapshot.http.series, true)", self.js)
        self.assertIn("updateChart('traffic', snapshot.traffic.series)", self.js)

    def test_todos_los_iconos_existen_en_el_webfont(self):
        # Un `ti-*` que no está en el CSS no renderiza nada: el botón o la card
        # parecen no tener icono y nadie lo nota hasta verlo en el navegador.
        base = settings.BASE_DIR
        css = (base / 'static/dist/css/tabler-icons.min.css').read_text()
        validos = set(re.findall(r'\.ti-([a-z0-9-]+)::?before', css))
        archivos = (
            base / 'apps/dashboard/templates/pages/dashboard/monitoring.html',
            base / 'static/dist/js/site-monitoring.js',
        )
        for archivo in archivos:
            usados = set(re.findall(r'\bti-([a-z0-9-]+)', archivo.read_text()))
            with self.subTest(archivo=archivo.name):
                self.assertFalse(
                    usados - validos, f'iconos inexistentes: {sorted(usados - validos)}'
                )


class MonitoringClockTests(TestCase):
    """La configuración horaria del sitio llega hasta el panel."""

    def setUp(self):
        SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})
        self.client.force_login(superuser())

    def _configure(self, **fields):
        site = SiteConfiguration.get_instance()
        for key, value in fields.items():
            setattr(site, key, value)
        site.save()

    def _last_slot_label(self):
        response = self.client.get(reverse('dashboard:monitoring_data'))
        self.assertEqual(response.status_code, 200)
        return response.json()['uptime']['slots'][-1]['label']

    def test_formato_de_12_horas(self):
        self._configure(time_format='12')
        self.assertRegex(self._last_slot_label(), r'^\d{2}:\d{2} (AM|PM)$')

    def test_formato_de_24_horas(self):
        self._configure(time_format='24')
        self.assertRegex(self._last_slot_label(), r'^\d{2}:\d{2}$')


class RequestMetricsMiddlewareTests(TestCase):
    def setUp(self):
        SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})

    @override_settings(MONITORING_ENABLED=True)
    def test_registra_la_peticion_servida(self):
        self.client.get('/tiempo/hoy/')
        self.assertTrue(RequestMetric.objects.filter(path='/tiempo/hoy/').exists())

    @override_settings(MONITORING_ENABLED=True)
    def test_no_registra_su_propio_endpoint(self):
        self.client.force_login(superuser())
        self.client.get(reverse('dashboard:monitoring_data'))
        self.assertFalse(RequestMetric.objects.filter(path='/dashboard/monitoring/data/').exists())

    def test_con_la_captura_apagada_no_escribe(self):
        self.client.get('/tiempo/hoy/')
        self.assertEqual(RequestMetric.objects.count(), 0)


class BeaconInjectionTests(TestCase):
    def setUp(self):
        SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})

    @override_settings(MONITORING_ENABLED=True)
    def test_las_paginas_publicas_incluyen_el_beacon(self):
        response = self.client.get('/tiempo/hoy/')
        self.assertContains(response, 'rum-beacon.js')
        self.assertContains(response, '/rum/collect/')

    def test_con_la_captura_apagada_no_se_inyecta(self):
        response = self.client.get('/tiempo/hoy/')
        self.assertNotContains(response, 'rum-beacon.js')
