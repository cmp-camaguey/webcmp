from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AccountabilityReport

User = get_user_model()


class AccountabilityReportDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='pass12345',  # pragma: allowlist secret
            first_name='Admin',
            last_name='User',
        )
        self.client.force_login(self.user)

    def test_create_accountability_report(self):
        response = self.client.post(
            reverse('core:accountability_report_create'),
            {
                'year': 2025,
                'title': 'Informe 2025',
                'description': 'Rendición de cuenta anual',
                'is_published': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        report = AccountabilityReport.objects.get(year=2025)
        self.assertTrue(report.is_published)
        self.assertEqual(report.title, 'Informe 2025')

    def test_public_page_shows_published_report(self):
        AccountabilityReport.objects.create(year=2025, title='Informe 2025', is_published=True)
        response = self.client.get(reverse('home:institution_accountability'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informe 2025')

    def test_public_page_hides_unpublished_report(self):
        AccountabilityReport.objects.create(year=2025, title='Borrador 2025', is_published=False)
        response = self.client.get(reverse('home:institution_accountability'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Borrador 2025')
