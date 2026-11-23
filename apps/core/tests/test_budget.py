from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import BudgetLine, BudgetPeriod

User = get_user_model()


class BudgetPeriodModelTests(TestCase):
    def test_execution_percent(self):
        period = BudgetPeriod.objects.create(year=2026, title='Presupuesto 2026')
        line = BudgetLine.objects.create(
            period=period, category='Personal', planned_amount=100, executed_amount=50
        )
        self.assertEqual(line.execution_percent, 50)


class BudgetDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='pass12345',  # pragma: allowlist secret
            first_name='Admin',
            last_name='User',
        )
        self.client.force_login(self.user)

    def test_create_budget_period(self):
        response = self.client.post(
            reverse('core:budget_period_create'),
            {
                'year': 2026,
                'title': 'Presupuesto 2026',
                'description': 'Detalle',
                'is_published': 'on',
                'lines-TOTAL_FORMS': '1',
                'lines-INITIAL_FORMS': '0',
                'lines-MIN_NUM_FORMS': '0',
                'lines-MAX_NUM_FORMS': '1000',
                'lines-0-category': 'Gastos de personal',
                'lines-0-planned_amount': '1000.00',
                'lines-0-executed_amount': '800.00',
                'lines-0-order': '0',
            },
        )
        self.assertEqual(response.status_code, 302)
        period = BudgetPeriod.objects.get(year=2026)
        self.assertTrue(period.is_published)
        self.assertEqual(period.lines.count(), 1)

    def test_public_page_shows_published_period(self):
        period = BudgetPeriod.objects.create(year=2026, title='Presupuesto 2026', is_published=True)
        BudgetLine.objects.create(
            period=period, category='Personal', planned_amount=100, executed_amount=80
        )
        response = self.client.get(reverse('home:institution_budget'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Presupuesto 2026')
        self.assertContains(response, 'Personal')
