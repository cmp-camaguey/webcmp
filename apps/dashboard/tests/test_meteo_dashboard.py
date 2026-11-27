from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import SiteConfiguration
from apps.dashboard.services.meteo_dashboard import (
    get_meteo_dashboard_context,
    has_meteo_dashboard_access,
    normalize_meteo_range,
)
from apps.meteo.models import Forecasts


def disable_maintenance_mode():
    SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})


def _grant(model, user, codename):
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(model)
    user.user_permissions.add(ct.permission_set.get(codename=codename))


class MeteoDashboardServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()

    def test_normalize_range(self):
        self.assertEqual(normalize_meteo_range('7d'), '7d')
        self.assertEqual(normalize_meteo_range('30d'), '30d')
        self.assertEqual(normalize_meteo_range('3m'), '3m')
        self.assertEqual(normalize_meteo_range('bad'), '7d')

    def test_access(self):
        su = User.objects.create_superuser(
            'msu', 'msu@x.com', 'pass', first_name='A', last_name='B'
        )
        self.assertTrue(has_meteo_dashboard_access(su))
        u = User.objects.create_user('mu', 'mu@x.com', 'pass', first_name='A', last_name='B')
        self.assertFalse(has_meteo_dashboard_access(u))
        _grant(Forecasts, u, 'view_forecast')
        u = User.objects.get(pk=u.pk)
        self.assertTrue(has_meteo_dashboard_access(u))

    def test_context_defaults(self):
        ctx = get_meteo_dashboard_context()
        self.assertEqual(ctx['selected_range'], '7d')
        self.assertIn('latest_forecast', ctx)
        self.assertIn('latest_alerts', ctx)
        self.assertIn('has_forecasts', ctx)


class MeteoDashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()
        cls.url = reverse('dashboard:meteorologia')

    def test_anonymous_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_no_perm_403(self):
        user = User.objects.create_user('mnop', 'mnop@x.com', 'pass', first_name='A', last_name='B')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_forecast_perm_access(self):
        user = User.objects.create_user(
            'mfp', 'mfp@x.com', 'pass', first_name='A', last_name='B', is_staff=True
        )
        _grant(Forecasts, user, 'view_forecast')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_renders(self):
        user = User.objects.create_superuser(
            'mren', 'mren@x.com', 'pass', first_name='A', last_name='B'
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, 'Resumen Meteorológico')
        self.assertContains(response, 'Alertas Activas')


class MeteoDashboardRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()

    def test_meteo_only_staff_redirects(self):
        user = User.objects.create_user(
            'mroute', 'mroute@x.com', 'pass', first_name='A', last_name='B', is_staff=True
        )
        _grant(Forecasts, user, 'view_forecast')
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(
            response, reverse('dashboard:meteorologia'), fetch_redirect_response=False
        )

    def test_superuser_keeps_index(self):
        user = User.objects.create_superuser(
            'mrisu', 'mrisu@x.com', 'pass', first_name='A', last_name='B'
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
