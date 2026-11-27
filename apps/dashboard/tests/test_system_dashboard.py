from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import SiteConfiguration
from apps.dashboard.services.system_dashboard import (
    get_system_dashboard_context,
    has_system_dashboard_access,
)


def disable_maintenance_mode():
    SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})
    SiteConfiguration.objects.update(maintenance_mode=False)


class SystemDashboardServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()

    def test_access_superuser(self):
        su = User.objects.create_superuser(
            'ssu', 'ssu@x.com', 'pass', first_name='A', last_name='B'
        )
        self.assertTrue(has_system_dashboard_access(su))

    def test_access_denied_regular(self):
        u = User.objects.create_user('snu', 'snu@x.com', 'pass', first_name='A', last_name='B')
        self.assertFalse(has_system_dashboard_access(u))

    @patch('apps.dashboard.services.system_dashboard._safe_backup_status', return_value=None)
    @patch('apps.dashboard.services.system_dashboard._safe_backup_manifest', return_value={})
    def test_context_defaults(self, _manifest, _status):
        ctx = get_system_dashboard_context()
        self.assertIn('maintenance_mode', ctx)
        self.assertIn('task_stats', ctx)
        self.assertIn('backup_info', ctx)
        self.assertIn('user_stats', ctx)
        self.assertIn('attention_items', ctx)
        self.assertEqual(ctx['task_stats']['error'], 0)


class SystemDashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()
        cls.url = reverse('dashboard:sistema')

    def test_anonymous_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_no_perm_403(self):
        user = User.objects.create_user('snp', 'snp@x.com', 'pass', first_name='A', last_name='B')
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    @patch('apps.dashboard.services.system_dashboard._safe_backup_status', return_value=None)
    @patch('apps.dashboard.services.system_dashboard._safe_backup_manifest', return_value={})
    def test_superuser_renders(self, _manifest, _status):
        user = User.objects.create_superuser(
            'sren', 'sren@x.com', 'pass', first_name='A', last_name='B'
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resumen del Sistema')


class SystemDashboardRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()

    @patch('apps.dashboard.services.system_dashboard._safe_backup_status', return_value=None)
    @patch('apps.dashboard.services.system_dashboard._safe_backup_manifest', return_value={})
    def test_activitylog_user_redirects(self, _manifest, _status):
        from django.contrib.contenttypes.models import ContentType

        from apps.core.models import ActivityLog

        user = User.objects.create_user(
            'sroute', 'sroute@x.com', 'pass', first_name='A', last_name='B', is_staff=True
        )
        ct = ContentType.objects.get_for_model(ActivityLog)
        user.user_permissions.add(ct.permission_set.get(codename='view_activitylog'))
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response, reverse('dashboard:sistema'), fetch_redirect_response=False)
