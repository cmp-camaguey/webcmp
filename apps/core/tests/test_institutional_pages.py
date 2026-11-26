from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.institutional_pages import PAGE_SCHEMAS
from apps.core.models import InstitutionalPage

User = get_user_model()


class InstitutionalPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='pass12345',  # pragma: allowlist secret
            first_name='Admin',
            last_name='User',
        )
        self.client.force_login(self.user)
        for page_key in PAGE_SCHEMAS:
            InstitutionalPage.objects.get_or_create(page_key=page_key, defaults={'blocks': {}})

    def test_list_view(self):
        response = self.client.get(reverse('core:institutional_page_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visión')

    def test_update_page(self):
        page = InstitutionalPage.objects.get(page_key='vision')
        response = self.client.post(
            reverse('core:institutional_page_update', args=[page.uuid]),
            {'hero_description': 'Nueva visión', 'section_title': 'Valores'},
        )
        self.assertEqual(response.status_code, 302)
        page.refresh_from_db()
        self.assertEqual(page.blocks['hero_description'], 'Nueva visión')

    def test_public_page_uses_block(self):
        page = InstitutionalPage.objects.get(page_key='vision')
        page.blocks = {'hero_description': 'Texto editable'}
        page.save()
        response = self.client.get(reverse('home:institution_vision'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Texto editable')
