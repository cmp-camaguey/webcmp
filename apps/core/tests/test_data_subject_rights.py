"""Tests para el modelo, formulario, vista y señales de solicitudes ARCO/ARCOP."""

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import CompanySettings, DataSubjectRequest
from apps.home.views.institucion.institucional.views import DataSubjectRightsForm


class DataSubjectRequestModelTests(TestCase):
    """Tests del modelo DataSubjectRequest."""

    def setUp(self):
        self.valid_data = {
            'request_type': DataSubjectRequest.RequestType.ACCESO,
            'subject_email': 'test@example.com',
            'subject_name': 'Juan Pérez',
            'subject_document': '12345678',
            'description': 'Quiero acceder a mis datos personales.',
        }

    def test_create_request(self):
        """Crear una solicitud válida."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        self.assertIsNotNone(request.uuid)
        self.assertEqual(request.status, DataSubjectRequest.Status.PENDIENTE)
        self.assertIsNone(request.completed_at)
        self.assertEqual(request.request_type, DataSubjectRequest.RequestType.ACCESO)

    def test_request_types(self):
        """Verificar todos los tipos de solicitud ARCO/ARCOP."""
        types = [
            DataSubjectRequest.RequestType.ACCESO,
            DataSubjectRequest.RequestType.RECTIFICACION,
            DataSubjectRequest.RequestType.CANCELACION,
            DataSubjectRequest.RequestType.OPOSICION,
            DataSubjectRequest.RequestType.PORTABILIDAD,
        ]
        for req_type in types:
            with self.subTest(req_type=req_type):
                data = {**self.valid_data, 'request_type': req_type}
                request = DataSubjectRequest.objects.create(**data)
                self.assertEqual(request.request_type, req_type)

    def test_status_choices(self):
        """Verificar todos los estados."""
        statuses = [
            DataSubjectRequest.Status.PENDIENTE,
            DataSubjectRequest.Status.EN_PROCESO,
            DataSubjectRequest.Status.COMPLETADA,
            DataSubjectRequest.Status.RECHAZADA,
        ]
        for status in statuses:
            with self.subTest(status=status):
                data = {**self.valid_data, 'status': status}
                request = DataSubjectRequest.objects.create(**data)
                self.assertEqual(request.status, status)

    def test_str_representation(self):
        """Test __str__ incluye tipo, email y estado (valores raw)."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        expected = 'acceso - test@example.com (pendiente)'
        self.assertEqual(str(request), expected)

    def test_get_absolute_url(self):
        """URL absoluta apunta a la gestión en dashboard."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        url = request.get_absolute_url()
        expected = reverse('core:data_subject_request_update', args=[request.pk])
        self.assertEqual(url, expected)

    def test_mark_completed_sets_timestamp(self):
        """Cambiar a COMPLETADA pone completed_at."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        request.status = DataSubjectRequest.Status.COMPLETADA
        request.save()
        self.assertIsNotNone(request.completed_at)

    def test_mark_rejected_sets_timestamp(self):
        """Cambiar a RECHAZADA pone completed_at."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        request.status = DataSubjectRequest.Status.RECHAZADA
        request.save()
        self.assertIsNotNone(request.completed_at)

    def test_mark_in_progress_does_not_set_timestamp(self):
        """Cambiar a EN_PROCESO no pone completed_at."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        request.status = DataSubjectRequest.Status.EN_PROCESO
        request.save()
        self.assertIsNone(request.completed_at)

    def test_default_ordering(self):
        """Orden por defecto: -created_at."""
        req1 = DataSubjectRequest.objects.create(**self.valid_data)
        req2 = DataSubjectRequest.objects.create(
            **{**self.valid_data, 'subject_email': 'other@example.com'}
        )
        requests = list(DataSubjectRequest.objects.all())
        self.assertEqual(requests[0], req2)
        self.assertEqual(requests[1], req1)

    def test_indexes_exist(self):
        """Verificar índices compuestos definidos en Meta."""
        indexes = DataSubjectRequest._meta.indexes
        index_fields = [tuple(idx.fields) for idx in indexes]
        self.assertIn(('status', 'created_at'), index_fields)
        self.assertIn(('subject_email', 'status'), index_fields)

    def test_custom_permissions(self):
        """Verificar permisos custom en español."""
        perms = DataSubjectRequest._meta.permissions
        perm_codes = [p[0] for p in perms]
        self.assertIn('view_datasubjectrequest', perm_codes)
        self.assertIn('add_datasubjectrequest', perm_codes)
        self.assertIn('change_datasubjectrequest', perm_codes)
        self.assertIn('delete_datasubjectrequest', perm_codes)
        # Verificar nombres en español
        perm_names = {p[0]: p[1] for p in perms}
        self.assertEqual(perm_names['view_datasubjectrequest'], 'Ver')
        self.assertEqual(perm_names['add_datasubjectrequest'], 'Añadir')
        self.assertEqual(perm_names['change_datasubjectrequest'], 'Editar')
        self.assertEqual(perm_names['delete_datasubjectrequest'], 'Eliminar')

    def test_default_permissions_empty(self):
        """default_permissions = () desactiva los 4 por defecto."""
        self.assertEqual(DataSubjectRequest._meta.default_permissions, ())


class DataSubjectRightsFormTests(TestCase):
    """Tests del formulario DataSubjectRightsForm."""

    def setUp(self):
        self.valid_data = {
            'request_type': DataSubjectRequest.RequestType.ACCESO,
            'subject_email': 'test@example.com',
            'subject_name': 'Juan Pérez',
            'subject_document': '12345678',
            'description': 'Quiero acceder a mis datos personales.',
        }

    def test_valid_form(self):
        """Formulario válido con todos los campos."""
        form = DataSubjectRightsForm(data=self.valid_data)
        self.assertTrue(form.is_valid())

    def test_required_fields(self):
        """Campos obligatorios."""
        required = ['request_type', 'subject_email', 'subject_name', 'description']
        for field in required:
            with self.subTest(field=field):
                data = {**self.valid_data}
                del data[field]
                form = DataSubjectRightsForm(data=data)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_subject_document_optional(self):
        """subject_document es opcional."""
        data = {**self.valid_data}
        del data['subject_document']
        form = DataSubjectRightsForm(data=data)
        self.assertTrue(form.is_valid())

    def test_invalid_email(self):
        """Email inválido falla."""
        data = {**self.valid_data, 'subject_email': 'no-es-email'}
        form = DataSubjectRightsForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('subject_email', form.errors)

    def test_email_normalization(self):
        """Email se normaliza a minúsculas."""
        data = {**self.valid_data, 'subject_email': 'TEST@EXAMPLE.COM'}
        form = DataSubjectRightsForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['subject_email'], 'test@example.com')

    def test_description_min_length(self):
        """Descripción muy corta falla."""
        data = {**self.valid_data, 'description': 'Corto'}
        form = DataSubjectRightsForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)

    def test_request_type_choices(self):
        """request_type acepta solo valores válidos."""
        valid_types = [c[0] for c in DataSubjectRequest.RequestType.choices]
        for req_type in valid_types:
            with self.subTest(req_type=req_type):
                data = {**self.valid_data, 'request_type': req_type}
                form = DataSubjectRightsForm(data=data)
                self.assertTrue(form.is_valid())

        data = {**self.valid_data, 'request_type': 'INVALIDO'}
        form = DataSubjectRightsForm(data=data)
        self.assertFalse(form.is_valid())

    def test_save_creates_request(self):
        """save() crea DataSubjectRequest con estado RECIBIDA."""
        form = DataSubjectRightsForm(data=self.valid_data)
        self.assertTrue(form.is_valid())
        request = form.save()
        self.assertIsInstance(request, DataSubjectRequest)
        self.assertEqual(request.status, DataSubjectRequest.Status.PENDIENTE)
        self.assertIsNotNone(request.uuid)


class DataSubjectRightsViewTests(TestCase):
    """Tests de la vista DataSubjectRightsView."""

    def setUp(self):
        from config.huey import huey

        self._old_immediate = huey.immediate
        huey.immediate = True
        self.url = reverse('home:institution_data_subject_rights')
        self.valid_data = {
            'request_type': DataSubjectRequest.RequestType.ACCESO,
            'subject_email': 'test@example.com',
            'subject_name': 'Juan Pérez',
            'subject_document': '12345678',
            'description': 'Quiero acceder a mis datos personales registrados en sus sistemas.',
        }

    def tearDown(self):
        from config.huey import huey

        huey.immediate = self._old_immediate

    def test_get_renders_form(self):
        """GET muestra el formulario."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ejercicio de derechos ARCO/ARCOP')
        self.assertContains(response, 'subject_email')
        self.assertContains(response, 'subject_name')
        self.assertContains(response, 'description')

    def test_post_valid_creates_request(self):
        """POST válido crea solicitud y redirige con mensaje."""
        with patch('apps.core.signals.send_email_task') as mock_send:
            response = self.client.post(self.url, self.valid_data, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DataSubjectRequest.objects.count(), 1)
        request = DataSubjectRequest.objects.first()
        self.assertEqual(request.subject_email, 'test@example.com')
        self.assertEqual(request.status, DataSubjectRequest.Status.PENDIENTE)
        # Verificar mensaje de éxito
        messages = list(response.context['messages'])
        self.assertTrue(any('recibida correctamente' in str(m) for m in messages))
        # Verificar que se llamó a send_email_task (confirmación al solicitante)
        self.assertTrue(mock_send.called)

    def test_post_invalid_shows_errors(self):
        """POST inválido muestra errores."""
        data = {**self.valid_data, 'subject_email': 'invalid'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DataSubjectRequest.objects.count(), 0)
        self.assertFormError(
            response.context['form'],
            'subject_email',
            'Introduzca una dirección de correo electrónico válida.',
        )

    def test_post_missing_required_shows_errors(self):
        """POST sin campos requeridos muestra errores."""
        data = {'subject_email': 'test@example.com'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DataSubjectRequest.objects.count(), 0)
        self.assertFormError(response.context['form'], 'subject_name', 'Este campo es requerido.')
        self.assertFormError(response.context['form'], 'description', 'Este campo es requerido.')
        self.assertFormError(response.context['form'], 'request_type', 'Este campo es requerido.')

    def test_template_used(self):
        """Usa el template correcto."""
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'pages/home/institution/data_subject_rights.html')

    def test_context_has_company_settings(self):
        """Contexto incluye CompanySettings."""
        CompanySettings.get_instance()
        response = self.client.get(self.url)
        self.assertIn('company', response.context)

    @override_settings(DEFAULT_FROM_EMAIL='noreply@test.com')
    def test_email_sent_to_requester(self):
        """Se envía email de confirmación al solicitante."""
        with patch('apps.core.signals.send_email_task') as mock_send:
            self.client.post(self.url, self.valid_data)

        self.assertTrue(mock_send.called)
        call_args = mock_send.call_args[0]
        self.assertEqual(call_args[3], ['test@example.com'])  # recipients
        self.assertIn('Confirmación', call_args[0])  # subject

    @override_settings(DEFAULT_FROM_EMAIL='noreply@test.com')
    def test_admin_notification_created(self):
        """Se crea notificación para admins (notify_superusers)."""
        with (
            patch('apps.core.notifications.notify_superusers') as mock_notify,
            patch('apps.core.signals.send_email_task'),
        ):
            self.client.post(self.url, self.valid_data)

        self.assertTrue(mock_notify.called)
        call_kwargs = mock_notify.call_args[1]
        self.assertEqual(call_kwargs['source'], 'data_subject_request')
        self.assertIn('Nueva solicitud', call_kwargs['title'])


class DataSubjectRequestSignalTests(TestCase):
    """Tests de las señales post_save para notificaciones."""

    def setUp(self):
        from config.huey import huey

        self._old_immediate = huey.immediate
        huey.immediate = True
        self.valid_data = {
            'request_type': DataSubjectRequest.RequestType.ACCESO,
            'subject_email': 'test@example.com',
            'subject_name': 'Juan Pérez',
            'subject_document': '12345678',
            'description': 'Quiero acceder a mis datos personales registrados en sus sistemas.',
        }

    def tearDown(self):
        from config.huey import huey

        huey.immediate = self._old_immediate

    @patch('apps.core.signals.send_email_task')
    @patch('apps.core.notifications.notify_superusers')
    def test_signal_on_create(self, mock_notify, mock_send):
        """Crear solicitud dispara notificación a admin y email a solicitante."""
        DataSubjectRequest.objects.create(**self.valid_data)

        # Verificar notify_superusers llamado
        self.assertTrue(mock_notify.called)
        # Verificar send_email_task llamado para confirmación
        self.assertTrue(mock_send.called)

    @patch('apps.core.signals.send_email_task')
    def test_signal_on_status_change_to_completed(self, mock_send):
        """Cambiar a COMPLETADA notifica al solicitante."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        mock_send.reset_mock()

        request.status = DataSubjectRequest.Status.COMPLETADA
        request.admin_notes = 'Su solicitud ha sido procesada.'
        request.save()

        self.assertTrue(mock_send.called)
        call_args = mock_send.call_args[0]
        self.assertIn('completada', call_args[0].lower())
        self.assertEqual(call_args[3], ['test@example.com'])

    @patch('apps.core.signals.send_email_task')
    def test_signal_on_status_change_to_rejected(self, mock_send):
        """Cambiar a RECHAZADA notifica al solicitante con info de apelación."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        mock_send.reset_mock()

        request.status = DataSubjectRequest.Status.RECHAZADA
        request.admin_notes = 'No se encontró información.'
        request.save()

        self.assertTrue(mock_send.called)
        call_args = mock_send.call_args[0]
        self.assertIn('rechazada', call_args[0].lower())
        html = call_args[1]
        self.assertIn('reclamación', html.lower())
        self.assertIn('direccion@cmw.insmet.cu', html)

    @patch('apps.core.signals.send_email_task')
    def test_signal_on_status_change_to_in_progress_no_email(self, mock_send):
        """Cambiar a EN_PROCESO no notifica al solicitante."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        mock_send.reset_mock()

        request.status = DataSubjectRequest.Status.EN_PROCESO
        request.save()

        self.assertFalse(mock_send.called)

    @patch('apps.core.signals.send_email_task')
    def test_signal_on_other_field_change_no_email(self, mock_send):
        """Cambiar admin_notes sin cambiar status no notifica."""
        request = DataSubjectRequest.objects.create(**self.valid_data)
        mock_send.reset_mock()

        request.admin_notes = 'Nota interna'
        request.save()

        self.assertFalse(mock_send.called)


class DataSubjectRequestDashboardViewTests(TestCase):
    """Tests de las vistas de gestión ARCO/ARCOP en el dashboard."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            'admin', 'admin@test.com', 'pass', first_name='Admin', last_name='User'
        )
        self.client.force_login(self.admin)
        self.request_obj = DataSubjectRequest.objects.create(
            request_type=DataSubjectRequest.RequestType.ACCESO,
            subject_email='user@test.com',
            subject_name='Usuario Test',
            subject_document='12345678',
            description='Quiero mis datos.',
        )

    def test_list_view_requires_login(self):
        self.client.logout()
        url = reverse('core:data_subject_request_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_list_view_accessible_for_superuser(self):
        url = reverse('core:data_subject_request_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario Test')
        self.assertContains(response, 'user@test.com')

    def test_update_view_accessible_for_superuser(self):
        url = reverse('core:data_subject_request_update', args=[self.request_obj.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestionar solicitud de derechos')

    def test_update_view_changes_status_and_notes(self):
        url = reverse('core:data_subject_request_update', args=[self.request_obj.pk])
        response = self.client.post(
            url,
            {
                'status': DataSubjectRequest.Status.COMPLETADA,
                'admin_notes': 'Procesado correctamente.',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, DataSubjectRequest.Status.COMPLETADA)
        self.assertEqual(self.request_obj.admin_notes, 'Procesado correctamente.')
        self.assertIsNotNone(self.request_obj.completed_at)


class DataSubjectRightsIntegrationTests(TestCase):
    """Tests de integración end-to-end."""

    def setUp(self):
        from config.huey import huey

        self._old_immediate = huey.immediate
        huey.immediate = True
        self.url = reverse('home:institution_data_subject_rights')
        self.valid_data = {
            'request_type': DataSubjectRequest.RequestType.RECTIFICACION,
            'subject_email': 'integration@test.com',
            'subject_name': 'Usuario Integración',
            'subject_document': '87654321',
            'description': 'Mis datos de contacto están incorrectos, necesito rectificarlos.',
        }

    def tearDown(self):
        from config.huey import huey

        huey.immediate = self._old_immediate

    @patch('apps.core.signals.send_email_task')
    @patch('apps.core.notifications.notify_superusers')
    def test_full_flow_create_to_complete(self, mock_notify, mock_send):
        """Flujo completo: crear -> procesar -> completar."""
        # 1. Usuario envía solicitud
        response = self.client.post(self.url, self.valid_data, follow=True)
        self.assertEqual(response.status_code, 200)
        request = DataSubjectRequest.objects.first()
        self.assertEqual(request.status, DataSubjectRequest.Status.PENDIENTE)

        # 2. Admin cambia a EN_PROCESO (sin email al usuario)
        mock_send.reset_mock()
        request.status = DataSubjectRequest.Status.EN_PROCESO
        request.save()
        self.assertFalse(mock_send.called)

        # 3. Admin completa la solicitud
        mock_send.reset_mock()
        request.status = DataSubjectRequest.Status.COMPLETADA
        request.admin_notes = 'Datos rectificados en el sistema.'
        request.save()
        self.assertTrue(mock_send.called)
        self.assertEqual(request.status, DataSubjectRequest.Status.COMPLETADA)
        self.assertIsNotNone(request.completed_at)

        # Verificar email de resolución
        call_args = mock_send.call_args[0]
        self.assertIn('completada', call_args[0].lower())
        self.assertIn('rectificados', call_args[1])

    @patch('apps.core.signals.send_email_task')
    @patch('apps.core.notifications.notify_superusers')
    def test_all_request_types_work(self, mock_notify, mock_send):
        """Todos los 5 tipos ARCO/ARCOP funcionan."""
        types = [
            DataSubjectRequest.RequestType.ACCESO,
            DataSubjectRequest.RequestType.RECTIFICACION,
            DataSubjectRequest.RequestType.CANCELACION,
            DataSubjectRequest.RequestType.OPOSICION,
            DataSubjectRequest.RequestType.PORTABILIDAD,
        ]
        for req_type in types:
            with self.subTest(req_type=req_type):
                data = {
                    **self.valid_data,
                    'request_type': req_type,
                    'subject_email': f'{req_type}@test.com',
                }
                response = self.client.post(self.url, data, follow=True)
                self.assertEqual(response.status_code, 200)
                request = DataSubjectRequest.objects.filter(
                    subject_email=data['subject_email']
                ).first()
                self.assertIsNotNone(request)
                self.assertEqual(request.request_type, req_type)
