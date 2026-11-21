"""Tests para avisos de cambios legales (Res. 58/2022 art. 8.d)."""

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TermsChangeNotice

User = get_user_model()


class TermsChangeNoticeModelTests(TestCase):
    """Tests del modelo TermsChangeNotice."""

    def future_date(self, days=120):
        return timezone.localdate() + datetime.timedelta(days=days)

    def test_create_notice(self):
        notice = TermsChangeNotice.objects.create(
            title='Actualización de política',
            description='Se actualizará la política de privacidad.',
            affected_document=TermsChangeNotice.AffectedDocument.PRIVACY_POLICY,
            effective_date=self.future_date(),
            is_published=False,
        )
        self.assertIsNotNone(notice.uuid)
        self.assertFalse(notice.is_published)

    def test_str_representation(self):
        notice = TermsChangeNotice.objects.create(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(),
        )
        self.assertEqual(str(notice), f'Cambio ({notice.effective_date})')

    def test_get_absolute_url(self):
        notice = TermsChangeNotice.objects.create(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(),
        )
        self.assertEqual(
            notice.get_absolute_url(),
            reverse('core:terms_change_notice_update', args=[notice.pk]),
        )

    def test_default_permissions_empty_and_custom_permissions(self):
        self.assertEqual(TermsChangeNotice._meta.default_permissions, ())
        codes = [p[0] for p in TermsChangeNotice._meta.permissions]
        self.assertEqual(
            codes,
            [
                'view_termschangenotice',
                'add_termschangenotice',
                'change_termschangenotice',
                'delete_termschangenotice',
            ],
        )

    def test_clean_rejects_published_with_less_than_90_days(self):
        notice = TermsChangeNotice(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(days=30),
            is_published=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            notice.full_clean()
        self.assertIn('effective_date', ctx.exception.message_dict)

    def test_clean_allows_published_with_90_days(self):
        notice = TermsChangeNotice(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(days=90),
            is_published=True,
        )
        notice.full_clean()  # should not raise

    def test_clean_allows_draft_with_short_date(self):
        notice = TermsChangeNotice(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(days=5),
            is_published=False,
        )
        notice.full_clean()  # should not raise

    def test_clean_allows_already_published_unchanged_after_window_passes(self):
        notice = TermsChangeNotice.objects.create(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(days=120),
            is_published=True,
        )
        notice.description = 'Descripción actualizada'
        notice.full_clean()  # should not raise, date unchanged

    def test_clean_rejects_effective_date_change_on_published_notice(self):
        notice = TermsChangeNotice.objects.create(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(days=120),
            is_published=True,
        )
        notice.effective_date = self.future_date(days=10)
        with self.assertRaises(ValidationError):
            notice.full_clean()

    def test_clean_rejects_when_publishing_existing_notice_without_90_days(self):
        notice = TermsChangeNotice.objects.create(
            title='Cambio',
            description='Desc',
            effective_date=self.future_date(days=10),
            is_published=False,
        )
        notice.is_published = True
        with self.assertRaises(ValidationError):
            notice.full_clean()


class TermsChangeNoticeDashboardViewTests(TestCase):
    """Tests de vistas dashboard para avisos de cambios legales."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='user',
            password='pass',  # pragma: allowlist secret
            first_name='User',
            last_name='Test',
            email='user@example.com',
        )
        self.staff = User.objects.create_user(
            username='staff',
            password='pass',  # pragma: allowlist secret
            first_name='Staff',
            last_name='Test',
            email='staff@example.com',
        )
        for codename in [
            'view_termschangenotice',
            'add_termschangenotice',
            'change_termschangenotice',
            'delete_termschangenotice',
        ]:
            perm = Permission.objects.get(codename=codename)
            self.staff.user_permissions.add(perm)
        self.staff = User.objects.get(pk=self.staff.pk)
        self.notice = TermsChangeNotice.objects.create(
            title='Aviso',
            description='Desc',
            effective_date=timezone.localdate() + datetime.timedelta(days=120),
            is_published=True,
        )

    def test_list_requires_permission(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('core:terms_change_notice_list'))
        self.assertEqual(response.status_code, 403)

    def test_list_ok_with_permission(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('core:terms_change_notice_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aviso')

    def test_create_ok_with_permission(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('core:terms_change_notice_create'),
            {
                'title': 'Nuevo aviso',
                'description': 'Detalle',
                'affected_document': TermsChangeNotice.AffectedDocument.ALL,
                'effective_date': (timezone.localdate() + datetime.timedelta(days=120)).isoformat(),
                'is_published': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TermsChangeNotice.objects.filter(title='Nuevo aviso').exists())

    def test_create_rejects_published_short_notice(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('core:terms_change_notice_create'),
            {
                'title': 'Aviso corto',
                'description': 'Detalle',
                'affected_document': TermsChangeNotice.AffectedDocument.ALL,
                'effective_date': (timezone.localdate() + datetime.timedelta(days=10)).isoformat(),
                'is_published': 'on',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TermsChangeNotice.objects.filter(title='Aviso corto').exists())

    def test_update_ok_with_permission(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('core:terms_change_notice_update', args=[self.notice.pk]),
            {
                'title': 'Aviso actualizado',
                'description': 'Detalle actualizado',
                'affected_document': TermsChangeNotice.AffectedDocument.PRIVACY_POLICY,
                'effective_date': self.notice.effective_date.isoformat(),
                'is_published': 'on',
            },
        )
        self.assertEqual(response.status_code, 302, response.get('Location', ''))
        self.notice.refresh_from_db()
        self.notice.refresh_from_db()
        self.assertEqual(self.notice.title, 'Aviso actualizado')

    def test_delete_ok_with_permission(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('core:terms_change_notice_delete', args=[self.notice.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TermsChangeNotice.objects.filter(pk=self.notice.pk).exists())


class TermsChangeNoticePublicViewTests(TestCase):
    """Tests de visibilidad pública de avisos de cambios legales."""

    def future_date(self, days=120):
        return timezone.localdate() + datetime.timedelta(days=days)

    def test_published_notice_shown_on_matching_page(self):
        TermsChangeNotice.objects.create(
            title='Cambio privacidad',
            description='Detalle cambio',
            affected_document=TermsChangeNotice.AffectedDocument.PRIVACY_POLICY,
            effective_date=self.future_date(),
            is_published=True,
        )
        response = self.client.get(reverse('home:institution_privacy_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cambio privacidad')

    def test_published_notice_not_shown_on_unrelated_page(self):
        TermsChangeNotice.objects.create(
            title='Cambio privacidad',
            description='Detalle cambio',
            affected_document=TermsChangeNotice.AffectedDocument.PRIVACY_POLICY,
            effective_date=self.future_date(),
            is_published=True,
        )
        response = self.client.get(reverse('home:institution_cookie_policy'))
        self.assertNotContains(response, 'Cambio privacidad')

    def test_all_documents_notice_shown_on_legal_pages(self):
        TermsChangeNotice.objects.create(
            title='Cambio global',
            description='Detalle global',
            affected_document=TermsChangeNotice.AffectedDocument.ALL,
            effective_date=self.future_date(),
            is_published=True,
        )
        for url_name in [
            'home:institution_legal_notice',
            'home:institution_privacy_policy',
            'home:institution_cookie_policy',
            'home:institution_data_subject_rights',
        ]:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, 'Cambio global')

    def test_draft_notice_not_shown(self):
        TermsChangeNotice.objects.create(
            title='Borrador',
            description='No visible',
            affected_document=TermsChangeNotice.AffectedDocument.ALL,
            effective_date=self.future_date(),
            is_published=False,
        )
        response = self.client.get(reverse('home:institution_legal_notice'))
        self.assertNotContains(response, 'Borrador')

    def test_past_effective_notice_not_shown(self):
        TermsChangeNotice.objects.create(
            title='Aviso vencido',
            description='Ya pasó',
            affected_document=TermsChangeNotice.AffectedDocument.ALL,
            effective_date=timezone.localdate() - datetime.timedelta(days=1),
            is_published=True,
        )
        response = self.client.get(reverse('home:institution_legal_notice'))
        self.assertNotContains(response, 'Aviso vencido')
