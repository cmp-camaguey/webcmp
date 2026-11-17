"""Go-to-top button contracts (shared base layout)."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import SiteConfiguration

BASE_DIR = Path(settings.BASE_DIR)


class GoToTopRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})
        cls.user = User.objects.create_superuser(
            'gotop_admin',
            'gotop_admin@example.com',
            'password',
            first_name='Go',
            last_name='Top',
        )

    def _assert_button(self, response):
        for fragment in (
            'class="t-go-to-top"',
            'aria-label="Go to top"',
            'data-bs-toggle="tooltip"',
            'data-bs-placement="bottom"',
            'title="Volver arriba"',
            'tabler-icon tabler-icon-chevron-up',
            '<path d="M6 15l6 -6l6 6"></path>',
            'dist/js/go-to-top.js?v=1',
        ):
            self.assertContains(response, fragment, msg_prefix=fragment)

    def test_home_renderiza_boton(self):
        response = self.client.get(reverse('home:index'))
        self.assertEqual(response.status_code, 200)
        self._assert_button(response)

    def test_dashboard_renderiza_boton(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self._assert_button(response)

    def test_boton_no_lleva_visible_en_el_markup(self):
        # Lo agrega el JS solo cuando hay scroll. Si viniera `visible` en el
        # HTML, la pagina mostraria la flecha siempre, incluso sin scroll.
        response = self.client.get(reverse('home:index'))
        self.assertNotContains(response, 'class="t-go-to-top visible"')


class GoToTopFileContractTests(TestCase):
    @staticmethod
    def _read(rel_path):
        return (BASE_DIR / rel_path).read_text(encoding='utf-8')

    def test_css_define_estado_visible_y_respeta_motion(self):
        css = self._read('static/dist/css/utils.css')
        self.assertIn('.t-go-to-top.visible', css)
        self.assertIn('prefers-reduced-motion: reduce', css)

    def test_js_solo_muestra_con_scroll_real_y_vuelve_arriba(self):
        js = self._read('static/dist/js/go-to-top.js')
        self.assertIn("querySelector('.t-go-to-top')", js)
        self.assertIn("classList.toggle('visible'", js)
        self.assertIn('window.scrollTo({ top: 0', js)
        self.assertIn('passive: true', js)

    def test_js_levanta_el_boton_sobre_el_footer_solo_al_final(self):
        # El footer del dashboard lleva las redes sociales en la esquina
        # inferior derecha. La clase `at-bottom` sube el boton lo justo al
        # llegar al final; el valor del offset vive en CSS, no en el JS.
        js = self._read('static/dist/js/go-to-top.js')
        self.assertIn('atBottom', js)
        self.assertIn("classList.toggle('at-bottom', atBottom)", js)
        css = self._read('static/dist/css/utils.css')
        self.assertIn('.t-go-to-top.at-bottom', css)
        self.assertIn('bottom: 4.5rem', css)
