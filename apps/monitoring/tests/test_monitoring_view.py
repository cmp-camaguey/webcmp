import re

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
        self.assertContains(response, 'Core Web Vitals')
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

    def test_la_consola_de_estado_expone_los_hooks_del_refresco(self):
        # El JS busca estos nodos para pausar, refrescar y teñir el estado.
        # Si el rediseño los pierde, el panel deja de actualizarse en vivo.
        for marker in (
            'id="monitoringRoot"',
            'data-status-label',
            'data-status-badge',
            'data-status-dot',
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
                    rf'class="table-responsive">\s*<table[^>]*>\s*'
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

    def test_errores_y_peso_son_tarjetas_compactas(self):
        # Estas dos tarjetas tienen poco contenido: si heredan la altura
        # mínima de las de media columna (28rem) quedan con un hueco grande.
        panel = self.html.split('id="monitoringRoot"', 1)[1]
        for titulo in ('Errores JavaScript', 'Peso de página y recursos lentos'):
            with self.subTest(titulo=titulo):
                pos = panel.index(titulo)
                apertura = panel.rfind('<div class="card ', 0, pos)
                clase = panel[apertura : panel.index('>', apertura)]
                self.assertIn('monitoring-compact-card', clase)
                self.assertNotIn('monitoring-half-card', clase)

        altura = r'\{\s*min-height:\s*(\d+)rem'
        compacta = int(re.search(r'\.monitoring-compact-card\s*' + altura, self.html).group(1))
        media = int(re.search(r'\.monitoring-half-card\s*' + altura, self.html).group(1))
        self.assertLess(compacta, media)


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
