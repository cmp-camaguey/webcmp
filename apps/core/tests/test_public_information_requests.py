from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Notification, PublicInformationRequest
from apps.home.views.institucion.institucional.views import PublicInformationRequestForm

User = get_user_model()


class PublicInformationRequestModelTests(TestCase):
    def test_create_request(self):
        obj = PublicInformationRequest.objects.create(
            subject_name='Juan Perez',
            subject_email='juan@example.com',
            subject_document='12345678',
            response_format=PublicInformationRequest.ResponseFormat.EMAIL,
            description='Solicito informacion sobre el presupuesto anual del centro.',
        )
        self.assertEqual(obj.status, PublicInformationRequest.Status.PENDIENTE)
        self.assertIsNone(obj.completed_at)
        self.assertTrue(obj.uuid)

    def test_completed_status_sets_completed_at(self):
        obj = PublicInformationRequest.objects.create(
            subject_name='Juan Perez',
            subject_email='juan@example.com',
            description='Solicito informacion sobre servicios.',
            response_format=PublicInformationRequest.ResponseFormat.EMAIL,
        )
        obj.status = PublicInformationRequest.Status.COMPLETADA
        obj.save()
        self.assertIsNotNone(obj.completed_at)

    def test_reopen_clears_completed_at(self):
        obj = PublicInformationRequest.objects.create(
            subject_name='Juan Perez',
            subject_email='juan@example.com',
            description='Solicito informacion sobre servicios.',
            response_format=PublicInformationRequest.ResponseFormat.EMAIL,
            status=PublicInformationRequest.Status.COMPLETADA,
        )
        obj.status = PublicInformationRequest.Status.PENDIENTE
        obj.save()
        obj.refresh_from_db()
        self.assertIsNone(obj.completed_at)


class PublicInformationRequestFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            'subject_name': 'Juan Perez',
            'subject_email': 'JUAN@EXAMPLE.COM',
            'subject_document': '12345678',
            'response_format': PublicInformationRequest.ResponseFormat.EMAIL,
            'description': 'Solicito informacion detallada sobre el presupuesto del centro.',
        }
        data.update(overrides)
        return data

    def test_valid_form_creates_request(self):
        form = PublicInformationRequestForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.subject_email, 'juan@example.com')
        self.assertEqual(obj.status, PublicInformationRequest.Status.PENDIENTE)

    def test_description_min_length(self):
        form = PublicInformationRequestForm(data=self.valid_data(description='Corto'))
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)

    def test_invalid_response_format(self):
        form = PublicInformationRequestForm(data=self.valid_data(response_format='fax'))
        self.assertFalse(form.is_valid())
        self.assertIn('response_format', form.errors)


class PublicInformationRequestPublicViewTests(TestCase):
    def setUp(self):
        self.url = reverse('home:institution_public_information')

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Formulario de solicitud')
        self.assertContains(response, 'Quince días hábiles')

    @patch('apps.core.signals.send_email_task')
    @patch('apps.core.notifications.notify_superusers')
    def test_post_creates_request(self, mock_notify, mock_send):
        response = self.client.post(
            self.url,
            {
                'subject_name': 'Juan Perez',
                'subject_email': 'juan@example.com',
                'subject_document': '',
                'response_format': PublicInformationRequest.ResponseFormat.SEDE,
                'description': 'Solicito informacion sobre los informes meteorologicos.',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PublicInformationRequest.objects.count(), 1)
        obj = PublicInformationRequest.objects.first()
        self.assertEqual(obj.response_format, PublicInformationRequest.ResponseFormat.SEDE)
        self.assertContains(response, 'Su solicitud ha sido recibida correctamente')


class PublicInformationRequestDashboardTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='pass12345',  # pragma: allowlist secret
            first_name='Admin',
            last_name='User',
        )
        self.client.force_login(self.superuser)
        with (
            patch('apps.core.signals.send_email_task'),
            patch('apps.core.notifications.notify_superusers'),
        ):
            self.request_obj = PublicInformationRequest.objects.create(
                subject_name='Juan Perez',
                subject_email='juan@example.com',
                description='Solicito informacion sobre convenios.',
                response_format=PublicInformationRequest.ResponseFormat.EMAIL,
            )

    def test_list_view_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('core:public_information_request_list'))
        self.assertEqual(response.status_code, 302)

    def test_list_view_for_superuser(self):
        response = self.client.get(reverse('core:public_information_request_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Juan Perez')

    @patch('apps.core.signals.send_email_task')
    @patch('apps.core.notifications.notify_superusers')
    def test_update_view_changes_status(self, mock_notify, mock_send):
        url = reverse('core:public_information_request_update', args=[self.request_obj.pk])
        response = self.client.post(
            url,
            {
                'status': PublicInformationRequest.Status.COMPLETADA,
                'responsible': self.superuser.pk,
                'due_date': '2026-12-15',
                'delivery_date': '2026-12-01',
                'delivery_format': PublicInformationRequest.ResponseFormat.EMAIL,
                'admin_notes': 'Entregada por correo.',
                'rejection_reason': '',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, PublicInformationRequest.Status.COMPLETADA)
        self.assertEqual(self.request_obj.admin_notes, 'Entregada por correo.')
        self.assertEqual(
            self.request_obj.delivery_format,
            PublicInformationRequest.ResponseFormat.EMAIL,
        )
        self.assertIsNotNone(self.request_obj.completed_at)

    @patch('apps.core.signals.send_email_task')
    @patch('apps.core.notifications.notify_superusers')
    def test_update_en_proceso_requires_responsible_and_note(self, mock_notify, mock_send):
        url = reverse('core:public_information_request_update', args=[self.request_obj.pk])
        response = self.client.post(
            url,
            {
                'status': PublicInformationRequest.Status.EN_PROCESO,
                'responsible': '',
                'due_date': '2026-12-15',
                'admin_notes': '',
                'rejection_reason': '',
                'delivery_format': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, PublicInformationRequest.Status.PENDIENTE)
        form = response.context['form']
        self.assertIn('responsible', form.errors)
        self.assertIn('admin_notes', form.errors)

    @patch('apps.core.signals.send_email_task')
    @patch('apps.core.notifications.notify_superusers')
    def test_update_rechazada_requires_reason(self, mock_notify, mock_send):
        url = reverse('core:public_information_request_update', args=[self.request_obj.pk])
        response = self.client.post(
            url,
            {
                'status': PublicInformationRequest.Status.RECHAZADA,
                'responsible': self.superuser.pk,
                'due_date': '2026-12-15',
                'admin_notes': 'No corresponde.',
                'rejection_reason': '',
                'delivery_format': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, PublicInformationRequest.Status.PENDIENTE)
        self.assertIn('rejection_reason', response.context['form'].errors)


class PublicInformationRequestNotificationRegressionTests(TestCase):
    def test_create_request_with_superuser_inserts_full_notification_source(self):
        User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='pass12345',  # pragma: allowlist secret
            first_name='Admin',
            last_name='User',
        )

        PublicInformationRequest.objects.create(
            subject_name='Juan Perez',
            subject_email='juan@example.com',
            description='Solicito informacion detallada sobre el presupuesto del centro.',
            response_format=PublicInformationRequest.ResponseFormat.EMAIL,
        )

        notification = Notification.objects.get(
            recipient__username='admin',
            source='public_information_request',
        )
        self.assertEqual(notification.source, 'public_information_request')
