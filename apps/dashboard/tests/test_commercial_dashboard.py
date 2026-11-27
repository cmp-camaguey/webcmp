"""Dashboard comercial por perfil (042).

El servicio concentra la lógica comercial que antes vivía en DashboardView.
"""

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.commercial.models import Invoice, Service, ServiceSubscription
from apps.commercial.tests.factories import (
    make_user,
    natural_customer,
)
from apps.core.models import SiteConfiguration
from apps.dashboard.services.commercial_dashboard import (
    get_commercial_dashboard_context,
    has_commercial_dashboard_access,
    normalize_income_range,
)


def disable_maintenance_mode():
    SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})


def _grant(model, user, codename):
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(model)
    user.user_permissions.add(ct.permission_set.get(codename=codename))


class HasCommercialDashboardAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()

    def test_superuser_has_access(self):
        user = User.objects.create_superuser('comsu', 'comsu@example.com', 'pass')
        self.assertTrue(has_commercial_dashboard_access(user))

    def test_view_subscription_has_access(self):
        user = make_user('comsub', first_name='A', last_name='B')
        _grant(ServiceSubscription, user, 'view_subscription')
        self.assertTrue(has_commercial_dashboard_access(user))

    def test_view_invoice_has_access(self):
        user = make_user('cominv', first_name='A', last_name='B')
        _grant(Invoice, user, 'view_invoice')
        self.assertTrue(has_commercial_dashboard_access(user))

    def test_client_without_perm_has_no_access(self):
        user = make_user('comclient', first_name='A', last_name='B')
        self.assertFalse(has_commercial_dashboard_access(user))

    def test_staff_without_commercial_perm_has_no_access(self):
        user = make_user('comstaff', first_name='A', last_name='B', is_staff=True)
        self.assertFalse(has_commercial_dashboard_access(user))


class NormalizeIncomeRangeTests(TestCase):
    def test_valid_ranges(self):
        for value in ('1m', '3m', '6m', '12m', 'all'):
            self.assertEqual(normalize_income_range(value), value)

    def test_invalid_falls_back_to_default(self):
        self.assertEqual(normalize_income_range('bad'), '12m')
        self.assertEqual(normalize_income_range(None), '12m')
        self.assertEqual(normalize_income_range(''), '12m')


class CommercialDashboardContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()
        cls.admin = User.objects.create_superuser('comadminctx', 'comadminctx@example.com', 'pass')
        cls.customer = natural_customer(
            user=make_user('comcustctx', first_name='Ana', last_name='Norte')
        )
        cls.service = Service.objects.create(
            user=cls.admin,
            title='Servicio Dashboard',
            summary='S',
            service_type='commercial',
            code='CDASH1',
            price=Decimal('50.00'),
        )

    def test_default_range_and_keys(self):
        context = get_commercial_dashboard_context(self.admin)
        self.assertEqual(context['income_range'], '12m')
        for key in (
            'month_income',
            'income_months',
            'income_billed_data',
            'income_paid_data',
            'active_subs',
            'pending_subs',
            'requested_subs',
            'active_subs_list',
            'pending_subs_list',
            'requested_subs_list',
        ):
            self.assertIn(key, context)

    def test_invalid_range_falls_back(self):
        context = get_commercial_dashboard_context(self.admin, income_range='nope')
        self.assertEqual(context['income_range'], '12m')

    def test_counts_only_record_active(self):
        ServiceSubscription.objects.create(
            customer=self.customer,
            service=self.service,
            payment_status='paid',
            start_date=timezone.now(),
            record_active=True,
        )
        ServiceSubscription.objects.create(
            customer=self.customer,
            service=self.service,
            payment_status='paid',
            start_date=timezone.now(),
            record_active=False,
        )
        ServiceSubscription.objects.create(
            customer=self.customer,
            service=self.service,
            payment_status='pending',
            start_date=timezone.now(),
            record_active=True,
        )
        ServiceSubscription.objects.create(
            customer=self.customer,
            service=self.service,
            payment_status='requested',
            start_date=timezone.now(),
            record_active=True,
        )
        context = get_commercial_dashboard_context(self.admin)
        self.assertEqual(context['active_subs'], 1)
        self.assertEqual(context['pending_subs'], 1)
        self.assertEqual(context['requested_subs'], 1)

    def test_drill_down_lists_are_limited_and_stable(self):
        service2 = Service.objects.create(
            user=self.admin,
            title='Servicio Dashboard 2',
            summary='S',
            service_type='commercial',
            code='CDASH2',
            price=Decimal('50.00'),
        )
        # create 25 paid subs
        for i in range(25):
            c = natural_customer(
                user=make_user(f'bulk{i}', first_name=f'Name{i}', last_name=f'Last{i}'),
                identity_document=f'990000{i:05d}',
                account=f'900000{i:010d}',
            )
            ServiceSubscription.objects.create(
                customer=c,
                service=service2,
                payment_status='paid',
                start_date=timezone.now(),
                record_active=True,
            )
        context = get_commercial_dashboard_context(self.admin)
        active = json.loads(context['active_subs_list'])
        self.assertLessEqual(len(active), 20)

    def test_income_series_are_json(self):
        context = get_commercial_dashboard_context(self.admin, income_range='3m')
        months = json.loads(context['income_months'])
        billed = json.loads(context['income_billed_data'])
        paid = json.loads(context['income_paid_data'])
        self.assertEqual(len(months), 3)
        self.assertEqual(len(billed), 3)
        self.assertEqual(len(paid), 3)


class CommercialDashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()
        cls.url = reverse('dashboard:commercial')

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_user_without_commercial_perm_gets_403(self):
        user = make_user('nocomm', first_name='A', last_name='B', is_staff=True)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_client_without_commercial_perm_gets_403(self):
        user = make_user('clientnocomm', first_name='A', last_name='B')
        from django.contrib.auth.models import Group

        group = Group.objects.get_or_create(name='Clientes')[0]
        user.groups.add(group)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_client_with_commercial_perm_gets_403(self):
        user = make_user('clientwithcomm', first_name='A', last_name='B')
        from django.contrib.auth.models import Group

        group = Group.objects.get_or_create(name='Clientes')[0]
        user.groups.add(group)
        _grant(ServiceSubscription, user, 'view_subscription')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_access(self):
        user = User.objects.create_superuser(
            'comvsu', 'comvsu@example.com', 'pass', first_name='A', last_name='B'
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['segment'], 'dashboard_comercial')

    def test_view_subscription_can_access(self):
        user = make_user('comvsub', first_name='A', last_name='B', is_staff=True)
        _grant(ServiceSubscription, user, 'view_subscription')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_view_invoice_can_access(self):
        user = make_user('comvinv', first_name='A', last_name='B', is_staff=True)
        _grant(Invoice, user, 'view_invoice')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_renders_key_sections(self):
        user = User.objects.create_superuser(
            'comrender', 'comrender@example.com', 'pass', first_name='A', last_name='B'
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, 'Resumen Comercial')
        self.assertContains(response, 'incomeChart')
        self.assertContains(response, 'subscriptionsChart')


class DashboardIndexRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        disable_maintenance_mode()
        cls.url = reverse('dashboard:index')

    def test_commercial_staff_redirects_to_commercial(self):
        user = make_user('idxcomm', first_name='A', last_name='B', is_staff=True)
        _grant(ServiceSubscription, user, 'view_subscription')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertRedirects(
            response, reverse('dashboard:commercial'), fetch_redirect_response=False
        )

    def test_client_keeps_index(self):
        user = make_user('idxclient', first_name='A', last_name='B')
        from django.contrib.auth.models import Group

        group = Group.objects.get_or_create(name='Clientes')[0]
        user.groups.add(group)
        # Create customer profile needed by dashboard
        natural_customer(user=user)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['segment'], 'dashboard')

    def test_superuser_keeps_index(self):
        user = User.objects.create_superuser(
            'idxsu', 'idxsu@example.com', 'pass', first_name='A', last_name='B'
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['segment'], 'dashboard')

    def test_staff_without_commercial_perm_keeps_index(self):
        user = make_user('idxplain', first_name='A', last_name='B', is_staff=True)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
