from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ComplianceProcedure

User = get_user_model()


class ComplianceProcedureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='pass12345',  # pragma: allowlist secret
            first_name='Admin',
            last_name='User',
        )
        self.client.force_login(self.user)
        for procedure_type in ComplianceProcedure.ProcedureType.values:
            ComplianceProcedure.objects.get_or_create(
                procedure_type=procedure_type,
                defaults={'title': procedure_type, 'body': ''},
            )

    def test_update_compliance_procedure(self):
        procedure = ComplianceProcedure.objects.get(
            procedure_type=ComplianceProcedure.ProcedureType.INCIDENT_RESPONSE
        )
        response = self.client.post(
            reverse('core:compliance_procedure_update', args=[procedure.uuid]),
            {'title': 'Incidentes', 'body': 'Contenido', 'is_published': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        procedure.refresh_from_db()
        self.assertTrue(procedure.is_published)
        self.assertEqual(procedure.title, 'Incidentes')

    def test_public_page_shows_published_procedure(self):
        procedure = ComplianceProcedure.objects.get(
            procedure_type=ComplianceProcedure.ProcedureType.BACKUP_RESTORE
        )
        procedure.title = 'Respaldo'
        procedure.body = 'Detalle'
        procedure.is_published = True
        procedure.save()
        response = self.client.get(reverse('home:institution_backup_restore'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Respaldo')
        self.assertContains(response, 'Detalle')
