import json
import os
import re
import shutil
import stat
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.core.env_apply import (
    PENDING_GRACE_SECONDS,
    RUN_STALE_SECONDS,
    ApplyRequestPendingError,
    apply_status,
    can_request,
    pending_request,
    request_apply,
)
from apps.core.env_config import (
    EDITABLE_FIELDS,
    SECRET_MASK,
    as_bool,
    build_env_preview,
    build_environment,
    effective_value,
    same_value,
    secret_status,
    strip_url_credentials,
)
from apps.core.env_file import is_writable, read_env_file, update_env_file
from apps.core.models import ActivityLog, SiteConfiguration
from config.settings.base import resolve_ldap_enabled

CANNOT_DROP_PRIVILEGES = hasattr(os, 'geteuid') and os.geteuid() == 0


def _disable_maintenance():
    SiteConfiguration.objects.get_or_create(defaults={'maintenance_mode': False})


class LdapEnabledResolutionTests(SimpleTestCase):
    """El interruptor de LDAP no puede apagar la autenticación por accidente."""

    def test_explicit_flag_wins_over_the_server_uri(self):
        self.assertTrue(resolve_ldap_enabled({'LDAP_ENABLED': 'True', 'LDAP_SERVER_URI': ''}))
        self.assertFalse(
            resolve_ldap_enabled({'LDAP_ENABLED': 'False', 'LDAP_SERVER_URI': 'ldap://dc'})
        )

    def test_absent_flag_falls_back_to_the_server_uri(self):
        self.assertTrue(resolve_ldap_enabled({'LDAP_SERVER_URI': 'ldap://dc'}))
        self.assertFalse(resolve_ldap_enabled({}))

    def test_truthy_forms_are_accepted(self):
        for value in ('1', 'true', 'True', 'yes', 'on'):
            self.assertTrue(resolve_ldap_enabled({'LDAP_ENABLED': value}))


class EnvFileTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir, ignore_errors=True)
        self.path = Path(self.tempdir) / '.env'

    def _write(self, text, mode=0o600):
        self.path.write_text(text, encoding='utf-8')
        self.path.chmod(mode)

    def test_read_missing_file_returns_empty(self):
        self.assertEqual(read_env_file(self.path), {})

    def test_read_skips_comments_and_blank_lines(self):
        self._write('# comentario\n\nDEBUG=True\nDB_HOST=127.0.0.1\n')
        self.assertEqual(read_env_file(self.path), {'DEBUG': 'True', 'DB_HOST': '127.0.0.1'})

    def test_read_unquotes_values(self):
        self._write("DEFAULT_FROM_EMAIL='Centro <x@y.cu>'\n")
        self.assertEqual(read_env_file(self.path)['DEFAULT_FROM_EMAIL'], 'Centro <x@y.cu>')

    def test_update_preserves_comments_order_and_unknown_keys(self):
        original = (
            '# =====\n# sección\n# =====\nDEBUG=True\nDB_HOST=127.0.0.1\nCLAVE_AJENA=no-tocar\n'
        )
        self._write(original)

        changed = update_env_file(self.path, {'DEBUG': 'False'})

        self.assertEqual(changed, ['DEBUG'])
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            original.replace('DEBUG=True', 'DEBUG=False'),
        )

    def test_update_appends_missing_key(self):
        self._write('DEBUG=True\n')
        changed = update_env_file(self.path, {'NOTIFICATIONS_MAX_VISIBLE': '25'})
        self.assertEqual(changed, ['NOTIFICATIONS_MAX_VISIBLE'])
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            'DEBUG=True\nNOTIFICATIONS_MAX_VISIBLE=25\n',
        )

    def test_update_does_not_touch_commented_key(self):
        self._write('# NOTIFICATIONS_ENABLED=False\n')
        update_env_file(self.path, {'NOTIFICATIONS_ENABLED': 'True'})
        text = self.path.read_text(encoding='utf-8')
        self.assertIn('# NOTIFICATIONS_ENABLED=False', text)
        self.assertIn('\nNOTIFICATIONS_ENABLED=True\n', text)

    def test_update_preserves_inline_comment(self):
        self._write('DEBUG=True  # ojo con esto\n')
        update_env_file(self.path, {'DEBUG': 'False'})
        self.assertEqual(self.path.read_text(encoding='utf-8'), 'DEBUG=False  # ojo con esto\n')

    def test_update_quotes_values_with_spaces(self):
        self._write('SITE_URL=http://localhost:8000/\n')
        update_env_file(self.path, {'SITE_URL': 'https://cmp.cu/con espacio'})
        self.assertIn(
            "SITE_URL='https://cmp.cu/con espacio'", self.path.read_text(encoding='utf-8')
        )

    def test_update_rejects_newlines(self):
        self._write('DEBUG=True\n')
        with self.assertRaises(ValueError):
            update_env_file(self.path, {'SITE_URL': 'http://x.cu/\notra'})
        self.assertEqual(self.path.read_text(encoding='utf-8'), 'DEBUG=True\n')

    def test_update_preserves_file_mode(self):
        self._write('DEBUG=True\n', mode=0o640)
        update_env_file(self.path, {'DEBUG': 'False'})
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)

    def test_update_preserves_crlf(self):
        self.path.write_bytes(b'DEBUG=True\r\nDB_HOST=127.0.0.1\r\n')
        update_env_file(self.path, {'DEBUG': 'False'})
        self.assertEqual(self.path.read_bytes(), b'DEBUG=False\r\nDB_HOST=127.0.0.1\r\n')

    def test_is_writable_true_for_normal_file(self):
        self._write('DEBUG=True\n')
        self.assertTrue(is_writable(self.path))

    def test_is_writable_false_when_directory_is_read_only(self):
        if CANNOT_DROP_PRIVILEGES:
            self.skipTest('root ignora los permisos del directorio')
        self._write('DEBUG=True\n')
        self.path.parent.chmod(0o500)
        self.addCleanup(self.path.parent.chmod, 0o700)
        self.assertFalse(is_writable(self.path))


class EnvConfigTests(SimpleTestCase):
    def test_readonly_groups_include_reference_sections(self):
        environment = build_environment(environ={}, file_values={})
        # La info de "Aplicación" viaja dentro de la tarjeta editable "Sitio".
        self.assertEqual(
            [group['key'] for group in environment['groups']],
            ['domain', 'database', 'cache', 'backup'],
        )

    def test_editable_sections_have_no_lone_half_width_field(self):
        """Los campos a media columna van de a pares; un `full` cierra la fila."""
        grouped: dict[str, list[str]] = {}
        for spec in EDITABLE_FIELDS:
            grouped.setdefault(spec.group, []).append(spec.width)

        for group, widths in grouped.items():
            runs = []
            current = 0
            for width in widths:
                if width == 'full':
                    if current:
                        runs.append(current)
                    current = 0
                else:
                    current += 1
            if current:
                runs.append(current)
            for run in runs:
                self.assertEqual(run % 2, 0, msg=f'{group}: {run} campo(s) suelto(s)')

    def test_editable_groups_cover_expected_sections(self):
        groups = []
        for spec in EDITABLE_FIELDS:
            if spec.group not in groups:
                groups.append(spec.group)
        self.assertEqual(
            groups, ['app', 'notifications', 'email', 'ldap', 'updates', 'ftp', 'backup']
        )

    def test_email_ldap_and_updates_are_editable(self):
        editable = {spec.key for spec in EDITABLE_FIELDS}
        for key in (
            'EMAIL_HOST',
            'EMAIL_PORT',
            'EMAIL_USE_TLS',
            'EMAIL_USE_SSL',
            'EMAIL_HOST_USER',
            'EMAIL_HOST_PASSWORD',
            'DEFAULT_FROM_EMAIL',
            'LDAP_ENABLED',
            'LDAP_SERVER_URI',
            'LDAP_BIND_DN',
            'LDAP_BIND_PASSWORD',
            'LDAP_USER_SEARCH_BASE',
            'UPDATE_REPO_URL',
            'UPDATE_BRANCH_REF',
            'UPDATE_CHECK_TTL',
            'UPDATE_CHECK_TIMEOUT',
            'FTP_OBS_PASS',
        ):
            self.assertIn(key, editable)

    def test_boot_critical_settings_stay_out_of_the_whitelist(self):
        editable = {spec.key for spec in EDITABLE_FIELDS}
        for key in (
            'DEBUG',
            'PRODUCTION',
            'SECRET_KEY',
            'ENCRYPTION_KEY',
            'EMAIL_BACKEND',
            'DB_PASS',
            'ALLOWED_HOSTS',
            'CSRF_TRUSTED_ORIGINS',
            'CORS_ALLOWED_ORIGINS',
            'USE_REDIS_CACHE',
            'REDIS_URL',
        ):
            self.assertNotIn(key, editable)

    def test_ldap_effective_values_come_from_the_environment(self):
        environ = {'LDAP_SERVER_URI': 'ldap://dc.cmp.cu:389'}
        self.assertEqual(
            effective_value('LDAP_SERVER_URI', environ=environ), 'ldap://dc.cmp.cu:389'
        )

    def test_ldap_start_tls_falls_back_to_its_default(self):
        self.assertEqual(effective_value('LDAP_START_TLS', environ={}), 'True')

    def test_domain_group_shows_external_hostname(self):
        environment = build_environment(
            environ={'EXTERNAL_HOSTNAME': 'https://cmp.camaguey.cu'}, file_values={}
        )
        domain = next(group for group in environment['groups'] if group['key'] == 'domain')
        values = {item['label']: item['value'] for item in domain['items']}
        self.assertEqual(values['Host externo'], 'https://cmp.camaguey.cu')

    def test_secret_status_never_includes_values(self):
        secrets = secret_status(environ={'ENCRYPTION_KEY': 'clave-de-prueba'})
        for entry in secrets:
            self.assertEqual(set(entry), {'key', 'label', 'configured'})
        rendered = repr(secrets)
        self.assertNotIn('clave-de-prueba', rendered)

    def test_secret_status_reports_configured_flags(self):
        secrets = {entry['key']: entry['configured'] for entry in secret_status(environ={})}
        self.assertTrue(secrets['SECRET_KEY'])
        self.assertFalse(secrets['ENCRYPTION_KEY'])

    def test_editable_secrets_are_not_listed_as_readonly_secrets(self):
        keys = {entry['key'] for entry in secret_status(environ={})}
        self.assertNotIn('EMAIL_HOST_PASSWORD', keys)
        self.assertNotIn('LDAP_BIND_PASSWORD', keys)
        self.assertNotIn('FTP_OBS_PASS', keys)

    def test_redis_url_credentials_are_stripped(self):
        self.assertEqual(
            strip_url_credentials('redis://:secreto@cache.local:6379/1'),
            'redis://***@cache.local:6379/1',
        )

    def test_redis_url_without_credentials_is_unchanged(self):
        self.assertEqual(
            strip_url_credentials('redis://cache.local:6379/1'),
            'redis://cache.local:6379/1',
        )

    @override_settings(
        CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': 'redis://cache.local:6379/1',
            }
        }
    )
    def test_cache_group_reflects_effective_backend(self):
        environment = build_environment(environ={}, file_values={})
        cache = next(group for group in environment['groups'] if group['key'] == 'cache')
        values = {item['label']: item['value'] for item in cache['items']}
        self.assertEqual(values['Motor'], 'Redis')

    def test_effective_value_renders_bools_and_ints(self):
        self.assertEqual(effective_value('NOTIFICATIONS_ENABLED'), 'True')
        self.assertEqual(effective_value('NOTIFICATIONS_MAX_VISIBLE'), '10')

    def test_same_value_compares_bools_case_insensitively(self):
        spec = next(field for field in EDITABLE_FIELDS if field.kind == 'bool')
        self.assertTrue(same_value(spec, 'true', 'True'))
        self.assertFalse(same_value(spec, 'False', 'True'))

    def test_same_value_compares_ints(self):
        spec = next(field for field in EDITABLE_FIELDS if field.key == 'NOTIFICATIONS_MAX_VISIBLE')
        self.assertTrue(same_value(spec, ' 10 ', '10'))
        self.assertFalse(same_value(spec, '11', '10'))

    def test_pending_only_when_file_differs_from_effective(self):
        environment = build_environment(environ={}, file_values={'NOTIFICATIONS_MAX_VISIBLE': '25'})
        self.assertTrue(environment['pending']['NOTIFICATIONS_MAX_VISIBLE'])
        self.assertFalse(environment['pending']['NOTIFICATIONS_ENABLED'])

    def test_as_bool_accepts_common_forms(self):
        for value in ('1', 'true', 'True', 'yes', 'on'):
            self.assertTrue(as_bool(value))
        for value in ('0', 'false', '', None):
            self.assertFalse(as_bool(value))

    def test_env_preview_masks_secrets_and_skips_unknown_keys(self):
        lines = build_env_preview(
            {'DEBUG': 'False', 'PRODUCTION': '1', 'EXTERNAL_TOKEN': 'no-debe-aparecer'},
            {
                'EMAIL_HOST_PASSWORD': 'claveSmtpSecreta',  # pragma: allowlist secret
                'OTHER_API_TOKEN': 'otroSecreto',  # pragma: allowlist secret
            },
            {},
            'produccion',
        )
        text = '\n'.join(line['text'] for line in lines)

        self.assertIn(f'EMAIL_HOST_PASSWORD={SECRET_MASK}', text)
        self.assertNotIn('claveSmtpSecreta', text)
        self.assertNotIn('OTHER_API_TOKEN', text)
        self.assertNotIn('EXTERNAL_TOKEN', text)
        self.assertNotIn('otroSecreto', text)

    def test_env_preview_reports_profile_and_unconfigured_secrets(self):
        lines = build_env_preview({'DEBUG': 'True'}, {}, {}, 'desarrollo')
        text = '\n'.join(line['text'] for line in lines)

        self.assertIn('# Entorno: desarrollo', text)
        self.assertIn('DEBUG=True', text)
        self.assertNotIn('PRODUCTION=', text)
        self.assertIn('EMAIL_HOST_PASSWORD=(sin configurar)', text)

    def test_env_preview_uses_effective_value_when_key_is_absent(self):
        lines = build_env_preview({}, {}, {'SITE_URL': 'https://cmp.camaguey.cu/'}, 'pruebas')
        self.assertIn('SITE_URL=https://cmp.camaguey.cu/', [line['text'] for line in lines])


class EnvironmentViewTestBase(TestCase):
    """Andamiaje compartido por las dos vistas del panel de entorno."""

    def setUp(self):
        _disable_maintenance()
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir, ignore_errors=True)
        self.env_path = Path(self.tempdir) / '.env'
        self.env_path.write_text(
            '# comentario\nDEBUG=True\nDB_PASS=supersecreto\n', encoding='utf-8'
        )
        self.env_path.chmod(0o600)
        override = override_settings(ENV_FILE_PATH=self.env_path)
        override.enable()
        self.addCleanup(override.disable)

        self.url = reverse('core:environment_config')
        self.superuser = User.objects.create_user(
            username='root',
            password='x',
            email='root@cmp.cu',
            first_name='Root',
            last_name='User',
            is_staff=True,
            is_superuser=True,
        )
        self.staff = User.objects.create_user(
            username='staff',
            password='x',
            email='staff@cmp.cu',
            first_name='Staff',
            last_name='User',
            is_staff=True,
        )

    def _payload(self, **overrides):
        """Lo que enviaría el navegador con el formulario recién cargado.

        Se construye desde el `initial` real en vez de una lista fija: si se
        escribieran valores a mano, un cambio en el `.env` del entorno de
        desarrollo haría que los tests guardaran claves que nadie tocó.
        """
        form = self.client.get(self.url).context['form']
        data = {}
        for spec in EDITABLE_FIELDS:
            value = form.initial.get(spec.key)
            if spec.kind == 'bool':
                if value:
                    data[spec.key] = 'on'
            elif value is None:
                data[spec.key] = ''
            else:
                data[spec.key] = str(value)
        data.update(overrides)
        return data


class EnvironmentConfigViewTests(EnvironmentViewTestBase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_staff_without_superuser_gets_403(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_superuser_gets_the_page(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entorno del servidor')

    def test_page_never_renders_secret_values(self):
        self.env_path.write_text(
            '# comentario\nDEBUG=True\n'
            'DB_PASS=supersecreto\n'
            'EMAIL_HOST_PASSWORD=claveSmtpSecreta\n'
            'FTP_OBS_PASS=claveFtpSecreta\n',
            encoding='utf-8',
        )
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'supersecreto')
        self.assertNotContains(response, 'claveSmtpSecreta')
        self.assertNotContains(response, 'claveFtpSecreta')
        self.assertNotContains(response, effective_value('SECRET_KEY'))

    def test_password_fields_are_reported_as_configured_without_the_value(self):
        self.env_path.write_text('EMAIL_HOST_PASSWORD=claveSmtpSecreta\n', encoding='utf-8')
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertContains(response, 'Configurada')
        self.assertNotContains(response, 'claveSmtpSecreta')

    def test_blank_password_does_not_erase_the_stored_one(self):
        self.env_path.write_text('EMAIL_HOST_PASSWORD=claveVieja\n', encoding='utf-8')
        self.client.force_login(self.superuser)

        self.client.post(self.url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        text = self.env_path.read_text(encoding='utf-8')
        self.assertIn('EMAIL_HOST_PASSWORD=claveVieja', text)

    def test_new_password_is_written(self):
        self.env_path.write_text('EMAIL_HOST_PASSWORD=claveVieja\n', encoding='utf-8')
        self.client.force_login(self.superuser)

        self.client.post(self.url, self._payload(EMAIL_HOST_PASSWORD='claveNueva'))

        text = self.env_path.read_text(encoding='utf-8')
        self.assertIn('EMAIL_HOST_PASSWORD=claveNueva', text)
        self.assertNotIn('claveVieja', text)

    def test_email_section_and_ldap_section_are_editable(self):
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(
            self.url,
            self._payload(
                EMAIL_HOST='smtp.cmp.cu',
                EMAIL_PORT='2525',
                EMAIL_USE_TLS='on',
                EMAIL_USE_SSL='',
                LDAP_SERVER_URI='ldap://dc.cmp.cu:389',
                LDAP_USER_SEARCH_BASE='ou=users,dc=cmp,dc=cu',
                UPDATE_CHECK_TTL='600',
            ),
        )

        self.assertEqual(response.status_code, 302)
        text = self.env_path.read_text(encoding='utf-8')
        self.assertIn('EMAIL_HOST=smtp.cmp.cu', text)
        self.assertIn('EMAIL_PORT=2525', text)
        self.assertIn('LDAP_SERVER_URI=ldap://dc.cmp.cu:389', text)
        self.assertIn('UPDATE_CHECK_TTL=600', text)
        self.assertIn('# comentario', text)
        self.assertIn('DB_PASS=supersecreto', text)
        self.assertNotEqual(before, text)

    def test_post_rejects_starttls_and_implicit_tls_together(self):
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(
            self.url,
            self._payload(EMAIL_PORT='587', EMAIL_USE_TLS='on', EMAIL_USE_SSL='on'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'EMAIL_USE_SSL', self._tls_conflict_message()
        )
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)

    def test_post_rejects_port_465_without_implicit_tls(self):
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(self.url, self._payload(EMAIL_PORT='465', EMAIL_USE_SSL=''))

        self.assertEqual(response.status_code, 200)
        self.assertIn('EMAIL_USE_SSL', response.context['form'].errors)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)

    def test_post_rejects_ldap_server_without_search_base(self):
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(
            self.url,
            self._payload(
                LDAP_ENABLED='on',
                LDAP_SERVER_URI='ldap://dc.cmp.cu:389',
                LDAP_USER_SEARCH_BASE='',
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('LDAP_USER_SEARCH_BASE', response.context['form'].errors)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)

    def test_post_rejects_ldap_enabled_without_server(self):
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(
            self.url,
            self._payload(LDAP_ENABLED='on', LDAP_SERVER_URI=''),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('LDAP_SERVER_URI', response.context['form'].errors)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)

    def test_ldap_toggle_is_written(self):
        self.client.force_login(self.superuser)

        self.client.post(
            self.url,
            self._payload(
                LDAP_ENABLED='on',
                LDAP_SERVER_URI='ldap://dc.cmp.cu:389',
                LDAP_USER_SEARCH_BASE='ou=users,dc=cmp,dc=cu',
            ),
        )

        text = self.env_path.read_text(encoding='utf-8')
        self.assertIn('LDAP_ENABLED=True', text)

    @staticmethod
    def _tls_conflict_message():
        return (
            'STARTTLS y TLS implícito no pueden estar activos a la vez: el sitio '
            'no arrancaría. Use el 587 con STARTTLS o el 465 con TLS implícito.'
        )

    def test_form_fields_render_placeholders(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertContains(response, 'placeholder="Ej.: https://cmp.camaguey.cu/"')
        self.assertContains(response, 'placeholder="Ej.: smtp.cmp.cu"')
        self.assertContains(response, 'placeholder="Ej.: ldap://dc.cmp.cu:389"')

    def test_password_placeholder_does_not_reveal_the_stored_value(self):
        self.env_path.write_text('EMAIL_HOST_PASSWORD=claveSmtpSecreta\n', encoding='utf-8')
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertContains(response, 'placeholder="Ej.: contraseña nueva"')
        self.assertNotContains(response, 'claveSmtpSecreta')

    def test_page_does_not_render_variable_names(self):
        """La página habla en castellano: no publica identificadores de `settings`."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for name in (
            'SECRET_KEY',
            'ENCRYPTION_KEY',
            'DB_PASS',
            'ALLOWED_HOSTS',
            'CSRF_TRUSTED_ORIGINS',
            'CORS_ALLOWED_ORIGINS',
            'CONN_MAX_AGE',
            'EMAIL_BACKEND',
        ):
            self.assertNotIn(name, html)
        self.assertContains(self.client.get(self.url), 'Clave secreta de Django')

    def test_readonly_labels_are_not_identifiers(self):
        environment = build_environment(environ={}, file_values={})
        for group in environment['groups']:
            for item in group['items']:
                self.assertNotRegex(item['label'], r'^[A-Z0-9_]+$')

    def test_engine_names_are_not_module_paths(self):
        environment = build_environment(environ={}, file_values={})
        groups = {group['key']: group for group in environment['groups']}
        for key in ('database', 'cache'):
            values = {item['label']: item['value'] for item in groups[key]['items']}
            self.assertNotIn('.', values['Motor'])

    def test_sitio_card_carries_the_application_readonly_info(self):
        """Los datos de arranque viven en la tabla de referencia, sin títulos de tarjeta."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        self.assertIn('Referencia', html)
        self.assertIn('Perfil de configuración', html)
        self.assertIn('Zona horaria', html)
        self.assertNotIn('>Aplicación<', html)
        self.assertNotIn('Sitio y correo', html)
        self.assertNotIn('En ejecución y secretos fuera del panel', html)

    def test_field_width_follows_the_catalog(self):
        """Los valores largos ocupan la fila; los cortos comparten columna."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        self.assertEqual(self._column_of(html, 'SITE_URL'), 'col-12')
        self.assertEqual(self._column_of(html, 'DEFAULT_FROM_EMAIL'), 'col-12')
        self.assertEqual(self._column_of(html, 'EMAIL_USE_TLS'), 'col-md-6')
        self.assertEqual(self._column_of(html, 'UPDATE_CHECK_TTL'), 'col-md-6')
        self.assertEqual(self._column_of(html, 'LDAP_SERVER_URI'), 'col-md-6')

    def test_zone_two_uses_eight_and_four_columns(self):
        """Sitio/Correo ocupa 8 columnas y Notificaciones 4: los campos ya no compiten."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        self.assertIn('<div class="col-xl-8">', html)
        self.assertIn('<div class="col-xl-4">', html)
        self.assertNotIn('<div class="col-xl-6">', html)

    def test_notification_card_has_its_own_eyebrow(self):
        """El card que antes arrancaba con switches ahora identifica su sección."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        self.assertIn('<div class="environment-eyebrow mb-3">Notificaciones</div>', html)

    def test_integrations_layout_ftp_full_width_and_ldap_updates_side_by_side(self):
        """FTP a lo ancho; LDAP y Actualizaciones en paralelo. Solo Referencia colapsa."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        ftp = html.index('Observaciones (FTP)')
        ldap = html.index('LDAP</div>')
        updates = html.index('Actualizaciones del panel')
        self.assertLess(ftp, ldap)
        self.assertLess(ldap, updates)

        for section_id in ('env-section-ftp', 'env-section-ldap', 'env-section-updates'):
            self.assertNotIn(f'id="{section_id}"', html, msg=section_id)

        self.assertIn('id="environment-reference"', html)
        self.assertIn('href="#environment-reference"', html)
        self.assertIn('data-bs-toggle="collapse"', html)

    def test_runtime_values_break_long_lines(self):
        """Los valores en ejecución no desbordan el campo en cards angostos."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        self.assertIn('En ejecución: <code class="text-break">', html)

    def test_email_fields_are_grouped_in_pairs(self):
        """Correo: servidor/puerto, usuario/clave, STARTTLS/TLS y remitente al final."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for first, second in (
            ('EMAIL_HOST', 'EMAIL_PORT'),
            ('EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD'),
            ('EMAIL_USE_TLS', 'EMAIL_USE_SSL'),
        ):
            self.assertEqual(self._column_of(html, first), 'col-md-6', msg=first)
            self.assertEqual(self._column_of(html, second), 'col-md-6', msg=second)
            start = html.index(f'id="id_{first}"')
            end = html.index(f'id="id_{second}"')
            self.assertNotIn('id="id_', html[start + 1 : end], msg=f'{first} / {second}')

        self.assertEqual(self._column_of(html, 'DEFAULT_FROM_EMAIL'), 'col-12')
        self.assertLess(
            html.index('id="id_EMAIL_USE_SSL"'),
            html.index('id="id_DEFAULT_FROM_EMAIL"'),
        )

    def test_ldap_switches_share_the_grid_and_superuser_closes_it(self):
        """Autenticación LDAP y STARTTLS van juntos; el grupo de superusuarios cierra la fila."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for first, second in (('LDAP_ENABLED', 'LDAP_START_TLS'),):
            self.assertEqual(self._column_of(html, first), 'col-md-6', msg=first)
            self.assertEqual(self._column_of(html, second), 'col-md-6', msg=second)
            start = html.index(f'id="id_{first}"')
            end = html.index(f'id="id_{second}"')
            self.assertNotIn('id="id_', html[start + 1 : end], msg=f'{first} / {second}')
        self.assertEqual(self._column_of(html, 'LDAP_SUPERUSER_GROUP'), 'col-12')

    def test_notification_switches_share_the_grid(self):
        """Los dos switches van juntos y bajan a una columna si no cabe el par."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for key in ('EMERGENCY_BANNER_ENABLED', 'NOTIFICATIONS_ENABLED'):
            self.assertEqual(self._column_of(html, key), 'col-md-6', msg=key)
        start = html.index('id="id_EMERGENCY_BANNER_ENABLED"')
        end = html.index('id="id_NOTIFICATIONS_ENABLED"')
        self.assertNotIn('id="id_', html[start + 1 : end])

    def test_field_labels_fit_on_one_line(self):
        """Etiquetas breves: sin contexto repetido ni unidades escritas."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for old in (
            'Franja de aviso de emergencia',
            'Entradas visibles en el navbar',
            'Antelación del aviso de vencimiento (horas)',
            'Retención de avisos leídos (días)',
            'Retención de avisos no leídos (días)',
            'Recordatorio de factura pendiente (días)',
            'Caché del chequeo (segundos)',
            'Timeout del chequeo (segundos)',
            'Repositorio de actualizaciones',
            'API del repositorio',
            'Caché del chequeo (seg.)',
            'Timeout del chequeo (seg.)',
            'STARTTLS en LDAP',
            'Base de búsqueda de usuarios',
            'Base de búsqueda de grupos',
            'Host FTP de observaciones',
        ):
            self.assertNotIn(old, html, msg=old)

        for new in (
            'Avisos de emergencia',
            'Avisos visibles',
            'Antelación vencimiento (h)',
            'Retención leídos (días)',
            'Retención no leídos (días)',
            'Recordatorio factura (días)',
            'Base de usuarios',
            'Base de grupos',
            'Host FTP',
        ):
            self.assertIn(new, html, msg=new)

        for key, label in (
            ('UPDATE_REPO_URL', 'Repositorio'),
            ('UPDATE_REPO_API', 'API'),
            ('UPDATE_CHECK_TTL', 'Caché (seg.)'),
            ('UPDATE_CHECK_TIMEOUT', 'Timeout (seg.)'),
        ):
            self.assertRegex(html, rf'for="id_{key}"[^>]*>{re.escape(label)}<', msg=key)

    def test_env_preview_button_sits_in_the_page_header(self):
        """El botón comparte posición con los de añadir en los listados."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        header = html.index('class="col-auto ms-auto d-print-none"')
        button = html.index('</i> Ver .env')
        self.assertLess(header, button)
        self.assertLess(button, html.index('class="card environment-console'))

    def test_notification_number_fields_use_full_width(self):
        """Los campos numéricos de avisos van en filas completas para no desalinearse."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for key in (
            'NOTIFICATIONS_MAX_VISIBLE',
            'NOTIFICATIONS_WARNING_HORIZON_HOURS',
            'NOTIFICATIONS_RETENTION_READ',
            'NOTIFICATIONS_RETENTION_UNREAD',
            'INVOICE_PENDING_REMINDER_DAYS',
        ):
            self.assertEqual(self._column_of(html, key), 'col-12', msg=key)

    def test_primary_button_is_labelled_aceptar(self):
        """Solo hay dos verbos en la página: "Aceptar" escribe y "Aplicar cambios" reinicia."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        self.assertIn('</i> Aceptar', html)
        self.assertNotIn('</i> Guardar', html)

    def test_page_identifies_the_environment_without_offering_a_switcher(self):
        """Cada servidor muestra su perfil; el panel nunca administra otro host."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertContains(response, 'Entorno actual:')
        self.assertIn(settings.IS_PRODUCTION and 'Producción' or 'Desarrollo', html)
        self.assertNotIn('data-variant=', html)

    def test_env_preview_uses_the_deploy_logs_console_style(self):
        self.env_path.write_text('EMAIL_HOST_PASSWORD=claveSmtpSecreta\n', encoding='utf-8')
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        html = response.content.decode()

        self.assertContains(response, 'Ver .env')
        self.assertIn('bg-dark text-white', html)
        self.assertIn('ti-terminal-2', html)
        self.assertIn('modal-dialog-scrollable', html)
        self.assertIn('env-console-body', html)
        self.assertIn(f'EMAIL_HOST_PASSWORD={SECRET_MASK}', html)
        self.assertNotIn('claveSmtpSecreta', html)

    def test_ftp_fields_share_the_grid(self):
        """El switch va solo y host/puerto y usuario/clave FTP comparten fila."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        self.assertEqual(self._column_of(html, 'OBS_AUTOMATIC'), 'col-12')
        for first, second in (
            ('FTP_OBS_HOST', 'FTP_OBS_PORT'),
            ('FTP_OBS_USER', 'FTP_OBS_PASS'),
        ):
            self.assertEqual(self._column_of(html, first), 'col-md-6', msg=first)
            self.assertEqual(self._column_of(html, second), 'col-md-6', msg=second)
            start = html.index(f'id="id_{first}"')
            end = html.index(f'id="id_{second}"')
            self.assertNotIn('id="id_', html[start + 1 : end], msg=f'{first} / {second}')

    def test_template_comments_do_not_leak_into_the_page(self):
        """Los comentarios de plantilla nunca llegan al HTML que ve el operador.

        Django 5.2 solo reconoce `{# ... #}` de una sola linea: uno partido en
        dos se renderiza como texto visible. Los comentarios largos usan el
        bloque `{% comment %}` para que no ocurra.
        """
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for fragment in (
            'Zona 1:',
            'Zona 2:',
            'Zona 3:',
            'Zona 4:',
            'No es un selector',
            'spaceless` evita',
            'Los switches van solos',
            'Campos editables de una seccion',
            'el modal comparte el form',
            'Preview del .env',
        ):
            self.assertNotIn(fragment, html, msg=fragment)
        self.assertNotIn('{#', html)

    def test_status_badges_use_colored_light_variants(self):
        """La consola usa bg-*-lt con color; nunca el gris de bg-secondary-lt."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for variant in ('bg-green-lt', 'bg-blue-lt', 'bg-orange-lt'):
            self.assertIn(variant, html)
        for variant in ('bg-secondary-lt', 'bg-success-lt', 'bg-warning-lt'):
            self.assertNotIn(variant, html)

    @override_settings(DEBUG=True, IS_PRODUCTION=False)
    def test_status_icons_share_one_style_and_only_the_color_changes(self):
        """Los iconos de estado van sin badge, con text-<color> según su significado."""
        status_path = Path(self.tempdir) / 'apply-status.json'
        request_path = Path(self.tempdir) / 'apply-request'
        status_path.write_text(json.dumps({'status': 'ok'}), encoding='utf-8')
        request_path.write_text(json.dumps({'requested_by': 'omar'}), encoding='utf-8')
        old = time.time() - PENDING_GRACE_SECONDS - 10
        os.utime(request_path, (old, old))
        override = override_settings(
            ENV_APPLY_STATUS_FILE=status_path,
            ENV_APPLY_REQUEST_FILE=request_path,
        )
        override.enable()
        self.addCleanup(override.disable)
        site = SiteConfiguration.get_instance()
        site.maintenance_mode = True
        site.save(update_fields=['maintenance_mode'])

        self.client.force_login(self.superuser)
        with patch('apps.core.views.env_config.is_writable', return_value=False):
            html = self.client.get(self.url).content.decode()

        section = html[
            html.index('Estado del entorno') : html.index('environment-eyebrow mb-3">Sitio')
        ]
        self.assertNotRegex(section, r'badge bg-[a-z]+-lt[^"]*"><i class="icon')
        icons = re.findall(r'<i class="icon ti ti-([a-z0-9-]+) text-([a-z]+)', section)
        self.assertTrue(icons)
        for name, color in icons:
            with self.subTest(name=name, color=color):
                self.assertIn(color, ('green', 'red', 'orange', 'blue', 'azure'))
        self.assertIn('ti-info-circle text-blue', section)
        self.assertIn('ti-alert-triangle text-red', section)
        self.assertIn('ti-circle-check text-green', section)
        self.assertIn('ti-tool text-orange mt-1', html)

    def test_pending_summary_sits_above_the_action_divider(self):
        """El resumen de cambios pendientes va sobre la línea y los botones."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        resumen = html.index('Sin cambios pendientes')
        divisor = html.index('border-top', resumen)
        aplicar = html.index('data-bs-target="#apply-changes-modal"')
        self.assertLess(resumen, divisor)
        self.assertLess(divisor, aplicar)

    def test_help_text_comes_before_the_running_value(self):
        """El orden es etiqueta, campo, ayuda y por último el valor en ejecución.

        Con la ayuda debajo del valor, el operador lee primero un dato que no
        puede cambiar y después la explicación del campo que sí edita.
        """
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        start = html.index('id="id_EMAIL_PORT"')
        block = html[start : html.index('id="id_', start + 1)]
        self.assertIn('El 587 usa STARTTLS', block)
        self.assertLess(block.index('El 587 usa STARTTLS'), block.index('En ejecución'))

    @staticmethod
    def _column_of(html: str, key: str) -> str:
        """Clase de grilla del contenedor del campo `key`.

        Se devuelve solo la primera clase: el contenedor puede llevar clases de
        espaciado (por ejemplo `mb-3`), que no cambian el ancho.
        """
        index = html.index(f'id="id_{key}"')
        start = html.rindex('class="col-', 0, index) + len('class="')
        return html[start : html.index('"', start)].split()[0]

    def test_page_does_not_render_server_paths(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        for value in (
            getattr(settings, 'ENV_FILE_PATH', ''),
            getattr(settings, 'EMAIL_FILE_PATH', ''),
            getattr(settings, 'UPDATE_DEPLOYED_SHA_FILE', ''),
            getattr(settings, 'UPDATE_STATUS_FILE', ''),
            getattr(settings, 'UPDATE_REQUEST_FILE', ''),
            getattr(settings, 'UPDATE_PROGRESS_FILE', ''),
            getattr(settings, 'ENV_APPLY_REQUEST_FILE', ''),
            getattr(settings, 'ENV_APPLY_STATUS_FILE', ''),
        ):
            if value:
                self.assertNotContains(response, str(value))

    @override_settings(DEBUG=True, IS_PRODUCTION=False)
    def test_development_page_shows_the_simulator_command(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertContains(response, 'Simulador de reinicio')
        self.assertContains(response, 'python manage.py dev_apply_env')

    @override_settings(DEBUG=False, IS_PRODUCTION=True)
    def test_production_page_does_not_show_the_simulator(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertNotContains(response, 'python manage.py dev_apply_env')
        self.assertNotContains(response, 'Simulador de reinicio')

    def test_post_writes_only_the_changed_key(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))
        self.assertEqual(response.status_code, 302)

        text = self.env_path.read_text(encoding='utf-8')
        self.assertIn('NOTIFICATIONS_MAX_VISIBLE=25', text)
        self.assertIn('# comentario', text)
        self.assertIn('DEBUG=True', text)
        self.assertIn('DB_PASS=supersecreto', text)
        self.assertNotIn('SITE_URL=', text)
        self.assertNotIn('FTP_OBS_HOST=', text)

    def test_post_with_invalid_value_does_not_touch_the_file(self):
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(self.url, self._payload(NOTIFICATIONS_MAX_VISIBLE='0'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)

    def test_post_rejects_non_http_site_url(self):
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(self.url, self._payload(SITE_URL='ftp://cmp.cu/'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)

    def test_post_logs_the_change_without_values(self):
        self.client.force_login(self.superuser)
        self.client.post(self.url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        entry = ActivityLog.objects.get(object_repr='Entorno del servidor')
        self.assertEqual(entry.user, self.superuser)
        self.assertIn('NOTIFICATIONS_MAX_VISIBLE', entry.message)
        self.assertNotIn('25', entry.message)

    def test_post_when_file_is_not_writable_does_not_touch_it(self):
        if CANNOT_DROP_PRIVILEGES:
            self.skipTest('root ignora los permisos del directorio')
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')
        self.env_path.parent.chmod(0o500)
        self.addCleanup(self.env_path.parent.chmod, 0o700)

        response = self.client.post(self.url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        self.assertEqual(response.status_code, 302)
        self.env_path.parent.chmod(0o700)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)
        self.assertFalse(ActivityLog.objects.filter(object_repr='Entorno del servidor').exists())

    def test_menu_shows_the_link_only_for_superusers(self):
        template = 'includes/dashboard/menu/_sistema.html'

        request = RequestFactory().get('/')
        request.user = self.superuser
        self.assertIn('Entorno del servidor', render_to_string(template, request=request))

        request.user = self.staff
        self.assertNotIn('Entorno del servidor', render_to_string(template, request=request))

    def test_verifier_no_secret_or_unknown_key_reaches_html(self):
        """Ni secretos del .env, ni de os.environ, ni claves de terceros llegan al HTML."""
        self.env_path.write_text(
            'EMAIL_HOST_PASSWORD=claveSmtpProbe\n'  # pragma: allowlist secret
            'LDAP_BIND_PASSWORD=claveBindProbe\n'  # pragma: allowlist secret
            'FTP_OBS_PASS=claveFtpProbe\n'  # pragma: allowlist secret
            'EXTERNAL_TOKEN=tokenTercerosProbe\n',  # pragma: allowlist secret
            encoding='utf-8',
        )
        environ = {
            'DEBUG': 'True',
            'PRODUCTION': '1',
            'SECRET_KEY': 'secretoEnvironProbe',  # pragma: allowlist secret
            'ENCRYPTION_KEY': 'cifradoEnvironProbe',  # pragma: allowlist secret
            'EXTERNAL_TOKEN': 'tokenEnvironProbe',  # pragma: allowlist secret
            'INJECTED_VALUE': '<script>alert(1)</script>',
        }
        self.client.force_login(self.superuser)
        with patch.dict('os.environ', environ, clear=False):
            html = self.client.get(self.url).content.decode()

        for needle in (
            'claveSmtpProbe',
            'claveBindProbe',
            'claveFtpProbe',
            'tokenTercerosProbe',
            'secretoEnvironProbe',
            'cifradoEnvironProbe',
            'tokenEnvironProbe',
            'INJECTED_VALUE',
            '<script>alert(1)</script>',
        ):
            self.assertNotIn(needle, html, msg=f'FILTRADO: {needle}')
        for key in ('EMAIL_HOST_PASSWORD', 'LDAP_BIND_PASSWORD', 'FTP_OBS_PASS'):
            self.assertIn(f'{key}={SECRET_MASK}', html)

    def test_verifier_no_template_comment_text_in_rendered_page(self):
        """Los fragmentos de los comentarios de plantilla no aparecen en la página."""
        self.client.force_login(self.superuser)
        html = self.client.get(self.url).content.decode()

        for fragment in (
            'Zona 1:',
            'Zona 2:',
            'Zona 3:',
            'Zona 4:',
            'No es un selector',
            'spaceless` evita',
            'Campos editables de una seccion',
            'Preview del .env',
            'formaction` y no',
        ):
            self.assertNotIn(fragment, html, msg=fragment)
        self.assertNotIn('{#', html)
        self.assertNotIn('{%', html)


class EnvApplyStatusTests(SimpleTestCase):
    """Estado del reinicio: lo que el panel muestra y lo que nunca inventa."""

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir, ignore_errors=True)
        self.path = Path(self.tempdir) / 'apply-status.json'

    def _write(self, payload):
        self.path.write_text(json.dumps(payload), encoding='utf-8')

    def test_missing_file_reports_nothing(self):
        self.assertIsNone(apply_status(self.path))

    def test_garbage_file_reports_nothing(self):
        self.path.write_text('{no es json', encoding='utf-8')
        self.assertIsNone(apply_status(self.path))

    def test_non_object_reports_nothing(self):
        self.path.write_text('[]', encoding='utf-8')
        self.assertIsNone(apply_status(self.path))

    def test_unknown_state_reports_nothing(self):
        self._write({'status': 'quizas'})
        self.assertIsNone(apply_status(self.path))

    def test_ok_state_reports_when_and_who(self):
        self._write(
            {
                'status': 'ok',
                'requested_by': 'omar',
                'started_at': '2026-11-10T12:00:00+00:00',
                'finished_at': '2026-11-10T12:00:05+00:00',
            }
        )
        status = apply_status(self.path)
        self.assertEqual(status['state'], 'ok')
        self.assertEqual(status['tone'], 'success')
        self.assertIn('Último reinicio completado', status['text'])
        self.assertIn('omar', status['text'])

    def test_failed_state_carries_the_reason(self):
        self._write({'status': 'failed', 'error': 'systemctl restart devolvio un error'})
        status = apply_status(self.path)
        self.assertEqual(status['state'], 'failed')
        self.assertEqual(status['tone'], 'danger')
        self.assertIn('systemctl restart devolvio un error', status['text'])

    def test_recent_running_is_in_progress(self):
        self._write({'status': 'running', 'started_at': datetime.now(UTC).isoformat()})
        status = apply_status(self.path)
        self.assertEqual(status['state'], 'running')
        self.assertEqual(status['tone'], 'info')
        self.assertIn('Reinicio en curso', status['text'])

    def test_old_running_is_reported_as_unconfirmed(self):
        started = datetime.now(UTC) - timedelta(seconds=RUN_STALE_SECONDS + 1)
        self._write({'status': 'running', 'started_at': started.isoformat()})
        status = apply_status(self.path)
        self.assertEqual(status['state'], 'stale')
        self.assertEqual(status['tone'], 'warning')
        self.assertIn('sin confirmar', status['text'])

    def test_running_without_start_instant_is_unconfirmed(self):
        self._write({'status': 'running'})
        self.assertEqual(apply_status(self.path)['state'], 'stale')

    def test_status_color_follows_the_badge_palette(self):
        expected = {'ok': 'green', 'failed': 'red'}
        for state, color in expected.items():
            with self.subTest(state=state):
                self._write({'status': state})
                self.assertEqual(apply_status(self.path)['color'], color)

        self._write({'status': 'running', 'started_at': datetime.now(UTC).isoformat()})
        self.assertEqual(apply_status(self.path)['color'], 'blue')

        started = datetime.now(UTC) - timedelta(seconds=RUN_STALE_SECONDS + 1)
        self._write({'status': 'running', 'started_at': started.isoformat()})
        self.assertEqual(apply_status(self.path)['color'], 'orange')

    def test_request_is_written_once(self):
        request_path = Path(self.tempdir) / 'apply-request'
        user = User(username='omar')

        payload = request_apply(request_path, user)

        self.assertEqual(payload['requested_by'], 'omar')
        self.assertTrue(request_path.exists())
        with self.assertRaises(ApplyRequestPendingError):
            request_apply(request_path, user)

    def test_can_request_follows_the_directory(self):
        self.assertTrue(can_request(Path(self.tempdir) / 'apply-request'))
        self.assertFalse(can_request(Path(self.tempdir) / 'no-existe' / 'apply-request'))


class EnvApplyPendingRequestTests(SimpleTestCase):
    """Petición de reinicio que nadie recogió.

    El ejecutor borra el archivo antes de hacer nada, así que una petición que
    sigue en disco ya no describe un reinicio en curso. Sin esta comprobación el
    panel no muestra nada, que es indistinguible de "nunca se pidió": el estado
    exacto de un servidor al que le falta la unidad que vigila el archivo.
    """

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir, ignore_errors=True)
        self.path = Path(self.tempdir) / 'apply-request'

    def _write(self, payload, age_seconds=0):
        self.path.write_text(json.dumps(payload), encoding='utf-8')
        if age_seconds:
            past = time.time() - age_seconds
            os.utime(self.path, (past, past))

    def test_missing_file_reports_nothing(self):
        self.assertIsNone(pending_request(self.path))

    def test_fresh_request_is_not_reported_as_orphaned(self):
        """Recién escrita, el ejecutor todavía puede recogerla."""
        self._write({'requested_by': 'omar'})

        self.assertIsNone(pending_request(self.path))

    def test_old_request_names_who_asked_and_when(self):
        self._write({'requested_by': 'omar'}, age_seconds=PENDING_GRACE_SECONDS + 10)

        pending = pending_request(self.path)

        self.assertIsNotNone(pending)
        self.assertEqual(pending['tone'], 'warning')
        self.assertIn('quedó sin recoger', pending['text'])
        self.assertIn('omar', pending['text'])
        self.assertIn('systemctl status webcmp-apply.path', pending['text'])

    def test_pending_color_matches_the_warning_badge(self):
        self._write({'requested_by': 'omar'}, age_seconds=PENDING_GRACE_SECONDS + 10)
        self.assertEqual(pending_request(self.path)['color'], 'orange')

    def test_simulator_text_points_to_the_command_instead_of_systemd(self):
        self._write({'requested_by': 'omar'}, age_seconds=PENDING_GRACE_SECONDS + 10)

        pending = pending_request(self.path, simulator=True)

        self.assertIn('quedó sin recoger', pending['text'])
        self.assertIn('python manage.py dev_apply_env', pending['text'])
        self.assertNotIn('systemctl', pending['text'])

    def test_old_request_without_readable_content_still_reports(self):
        """Lo que se informa es el archivo, no su contenido: el JSON roto no lo borra."""
        self.path.write_text('{no es json', encoding='utf-8')
        past = time.time() - (PENDING_GRACE_SECONDS + 10)
        os.utime(self.path, (past, past))

        pending = pending_request(self.path)

        self.assertIsNotNone(pending)
        self.assertNotIn('solicitada por', pending['text'])


class EnvironmentApplyViewTests(EnvironmentViewTestBase):
    """El botón "Aplicar": guarda y pide el reinicio en un solo paso."""

    def setUp(self):
        super().setUp()
        # Aplicar enciende el mantenimiento por su cuenta: los casos parten del
        # sitio en marcha, que es como el operador llega al panel.
        self.request_path = Path(self.tempdir) / 'apply-request'
        self.status_path = Path(self.tempdir) / 'apply-status.json'
        override = override_settings(
            ENV_APPLY_REQUEST_FILE=self.request_path,
            ENV_APPLY_STATUS_FILE=self.status_path,
        )
        override.enable()
        self.addCleanup(override.disable)
        self.apply_url = reverse('core:environment_apply')

    def _set_maintenance(self, enabled: bool):
        site = SiteConfiguration.get_instance()
        site.maintenance_mode = enabled
        site.save()

    def test_apply_saves_the_changes_and_requests_the_restart(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.apply_url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('NOTIFICATIONS_MAX_VISIBLE=25', self.env_path.read_text(encoding='utf-8'))
        payload = json.loads(self.request_path.read_text(encoding='utf-8'))
        self.assertEqual(payload['requested_by'], 'root')

    def test_apply_records_the_restart_in_the_audit_log(self):
        self.client.force_login(self.superuser)

        self.client.post(self.apply_url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        self.assertTrue(
            ActivityLog.objects.filter(
                object_repr='Entorno del servidor',
                message='Reinicio del servicio solicitado',
            ).exists()
        )

    def test_apply_without_changes_still_requests_the_restart(self):
        """Se pudo editar el archivo a mano y usar el botón solo para aplicar."""
        self.client.force_login(self.superuser)
        before = self.env_path.read_text(encoding='utf-8')

        response = self.client.post(self.apply_url, self._payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), before)
        self.assertTrue(self.request_path.exists())
        self.assertFalse(
            ActivityLog.objects.filter(message__startswith='Parámetros actualizados').exists()
        )

    def test_apply_with_a_pending_request_does_not_enqueue_twice(self):
        self.client.force_login(self.superuser)
        self.request_path.write_text('{"requested_by": "previo"}', encoding='utf-8')

        response = self.client.post(
            self.apply_url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'), follow=True
        )

        self.assertEqual(
            self.request_path.read_text(encoding='utf-8'), '{"requested_by": "previo"}'
        )
        self.assertContains(response, 'Ya hay un reinicio en curso')
        self.assertIn('NOTIFICATIONS_MAX_VISIBLE=25', self.env_path.read_text(encoding='utf-8'))

    def test_apply_with_an_invalid_form_does_not_request_anything(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.apply_url, self._payload(SITE_URL='ftp://cmp.cu/'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.request_path.exists())

    def test_apply_when_the_file_is_not_writable_does_not_request_anything(self):
        self.client.force_login(self.superuser)
        self.env_path.parent.chmod(0o500)
        self.addCleanup(self.env_path.parent.chmod, 0o700)

        response = self.client.post(self.apply_url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        self.assertEqual(response.status_code, 302)
        self.env_path.parent.chmod(0o700)
        self.assertFalse(self.request_path.exists())

    def test_staff_without_superuser_cannot_request_the_restart(self):
        self.client.force_login(self.superuser)
        payload = self._payload()
        self.client.force_login(self.staff)

        response = self.client.post(self.apply_url, payload)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.request_path.exists())

    def test_page_offers_the_button_next_to_the_save_button(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertTrue(response.context['can_apply'])
        self.assertContains(response, '</i> Aplicar')
        self.assertContains(response, f'formaction="{self.apply_url}"')

    def test_apply_modal_uses_the_delete_modal_cancel_pattern(self):
        self.client.force_login(self.superuser)

        html = self.client.get(self.url).content.decode()
        modal = html[html.index('id="apply-changes-modal"') :]

        self.assertIn('aria-label="Cerrar"', modal)
        self.assertIn('class="btn btn-link link-secondary me-auto"', modal)
        self.assertIn('data-bs-dismiss="modal">Cancelar', modal)
        self.assertIn('formaction="' + self.apply_url + '"', modal)
        self.assertIn('class="btn bg-blue-lt"', modal)
        self.assertIn('ti ti-check', modal)
        self.assertIn('</i> Aceptar', modal)
        self.assertNotIn('</i> Aplicar', modal)

    def test_page_disables_the_button_without_the_watcher(self):
        self.client.force_login(self.superuser)
        override = override_settings(
            ENV_APPLY_REQUEST_FILE=Path(self.tempdir) / 'no-existe' / 'apply-request'
        )
        override.enable()
        self.addCleanup(override.disable)

        response = self.client.get(self.url)

        self.assertFalse(response.context['can_apply'])
        self.assertContains(response, 'El reinicio automático no está disponible')

    def test_page_shows_the_last_restart_status(self):
        self.status_path.write_text(
            json.dumps({'status': 'ok', 'finished_at': '2026-11-10T12:00:05+00:00'}),
            encoding='utf-8',
        )
        self.client.force_login(self.superuser)

        self.assertContains(self.client.get(self.url), 'Último reinicio completado')

    def test_page_offers_the_apply_button_without_maintenance(self):
        """El operador ya no tiene que activar el mantenimiento a mano."""
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertTrue(response.context['can_apply'])
        self.assertContains(response, '</i> Aplicar')

    def test_page_warns_when_the_request_was_never_picked_up(self):
        """El síntoma del servidor sin la unidad: se pidió y no muestra nada."""
        self.request_path.write_text('{"requested_by": "omar"}', encoding='utf-8')
        past = time.time() - (PENDING_GRACE_SECONDS + 10)
        os.utime(self.request_path, (past, past))
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertContains(response, 'quedó sin recoger')
        self.assertContains(response, 'omar')

    def test_page_does_not_warn_right_after_requesting(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.apply_url, self._payload(), follow=True)

        self.assertNotContains(response, 'quedó sin recoger')
        self.assertContains(response, reverse('core:environment_maintenance_disable'))

    def test_apply_enables_maintenance_before_the_restart(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.apply_url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SiteConfiguration.get_instance().maintenance_mode)
        self.assertTrue(self.request_path.exists())
        self.assertIn('NOTIFICATIONS_MAX_VISIBLE=25', self.env_path.read_text(encoding='utf-8'))

    def test_apply_keeps_an_existing_maintenance_window(self):
        self._set_maintenance(True)
        self.client.force_login(self.superuser)

        self.client.post(self.apply_url, self._payload())

        self.assertTrue(SiteConfiguration.get_instance().maintenance_mode)

    def test_apply_restores_maintenance_when_the_restart_request_fails(self):
        """Si no se pudo pedir el reinicio, no se deja el sitio apagado."""
        self.client.force_login(self.superuser)
        override = override_settings(
            ENV_APPLY_REQUEST_FILE=Path(self.tempdir) / 'no-existe' / 'apply-request'
        )
        override.enable()
        self.addCleanup(override.disable)

        response = self.client.post(self.apply_url, self._payload(), follow=True)

        self.assertFalse(SiteConfiguration.get_instance().maintenance_mode)
        self.assertContains(response, 'el servidor no aceptó la petición de reinicio')

    def test_apply_with_an_invalid_form_does_not_enable_maintenance(self):
        self.client.force_login(self.superuser)

        self.client.post(self.apply_url, self._payload(SITE_URL='ftp://cmp.cu/'))

        self.assertFalse(SiteConfiguration.get_instance().maintenance_mode)

    def test_page_offers_two_actions_and_no_cancel_link(self):
        self.client.force_login(self.superuser)

        html = self.client.get(self.url).content.decode()

        self.assertIn('</i> Aceptar', html)
        self.assertIn('</i> Aplicar', html)
        self.assertRegex(html, r'class="btn bg-orange-lt"\s+data-bs-toggle="modal"')
        # El modal del navbar compartido tiene su propio "Cancelar"; lo que no
        # debe quedar es el botón de acción de esta página.
        self.assertNotIn(f'href="{self.url}" class="btn bg-azure-lt"', html)
        self.assertNotIn('ti-x"></i> Cancelar', html)
        self.assertIn('data-bs-target="#apply-changes-modal"', html)
        self.assertNotIn('confirm(', html)

    def test_page_shows_the_environment_status_console(self):
        self.client.force_login(self.superuser)

        self.assertContains(self.client.get(self.url), 'Estado del entorno')

    def test_save_still_works_without_touching_maintenance(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.url, self._payload(NOTIFICATIONS_MAX_VISIBLE='25'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('NOTIFICATIONS_MAX_VISIBLE=25', self.env_path.read_text(encoding='utf-8'))
        self.assertFalse(self.request_path.exists())
        self.assertFalse(SiteConfiguration.get_instance().maintenance_mode)

    def test_apply_ajax_saves_and_returns_restarting_payload(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.apply_url,
            self._payload(NOTIFICATIONS_MAX_VISIBLE='25'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['restarting'])
        self.assertEqual(data['redirect_url'], str(self.url))
        self.assertIn('entorno/aplicar/estado', data['status_url'])
        self.assertIn('NOTIFICATIONS_MAX_VISIBLE=25', self.env_path.read_text(encoding='utf-8'))
        self.assertTrue(SiteConfiguration.get_instance().maintenance_mode)

    def test_apply_ajax_with_invalid_form_returns_errors(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.apply_url,
            self._payload(SITE_URL='ftp://cmp.cu/'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('errors', data)
        self.assertFalse(SiteConfiguration.get_instance().maintenance_mode)

    def test_apply_ajax_with_pending_request_returns_conflict(self):
        self.client.force_login(self.superuser)
        self.request_path.write_text('{"requested_by": "previo"}', encoding='utf-8')

        response = self.client.post(
            self.apply_url,
            self._payload(NOTIFICATIONS_MAX_VISIBLE='25'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('redirect_url', data)
        self.assertIn('reinicio en curso', data['message'])

    def test_apply_ajax_when_restart_request_fails_restores_maintenance(self):
        self.client.force_login(self.superuser)
        override = override_settings(
            ENV_APPLY_REQUEST_FILE=Path(self.tempdir) / 'no-existe' / 'apply-request',
            ENV_APPLY_STATUS_FILE=self.status_path,
        )
        override.enable()
        self.addCleanup(override.disable)

        response = self.client.post(
            self.apply_url,
            self._payload(NOTIFICATIONS_MAX_VISIBLE='25'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertFalse(SiteConfiguration.get_instance().maintenance_mode)


class EnvironmentMaintenanceDisableViewTests(EnvironmentViewTestBase):
    """Salida directa del mantenimiento que enciende el propio panel."""

    def setUp(self):
        super().setUp()
        self._set_maintenance(True)
        self.disable_url = reverse('core:environment_maintenance_disable')

    def _set_maintenance(self, enabled: bool):
        site = SiteConfiguration.get_instance()
        site.maintenance_mode = enabled
        site.save()

    def test_superuser_can_disable_maintenance(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.disable_url)

        self.assertRedirects(response, self.url)
        self.assertFalse(SiteConfiguration.get_instance().maintenance_mode)
        self.assertTrue(
            ActivityLog.objects.filter(
                message='Modo mantenimiento desactivado desde el panel de entorno'
            ).exists()
        )

    def test_staff_cannot_disable_maintenance(self):
        self.client.force_login(self.staff)

        response = self.client.post(self.disable_url)

        # Con mantenimiento activo el middleware responde 503 antes de llegar a
        # la vista; sin la bandera, la vista responde 403 por no ser superusuario.
        self.assertEqual(response.status_code, 503)
        self.assertTrue(SiteConfiguration.get_instance().maintenance_mode)

        self._set_maintenance(False)
        self.assertEqual(self.client.post(self.disable_url).status_code, 403)
        self.assertFalse(SiteConfiguration.get_instance().maintenance_mode)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.superuser)

        self.assertEqual(self.client.get(self.disable_url).status_code, 405)
        self.assertTrue(SiteConfiguration.get_instance().maintenance_mode)

    def test_page_offers_the_way_out_while_in_maintenance(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertContains(response, self.disable_url)
        self.assertContains(response, 'Desactivar mantenimiento')

    def test_page_does_not_offer_the_way_out_without_maintenance(self):
        self._set_maintenance(False)
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertNotContains(response, self.disable_url)


class EnvironmentApplyStatusViewTests(EnvironmentViewTestBase):
    """Endpoint JSON usado por el panel para hacer polling del reinicio."""

    def setUp(self):
        super().setUp()
        self.status_url = reverse('core:environment_apply_status')
        self.request_path = Path(self.tempdir) / 'apply-request'
        self.status_path = Path(self.tempdir) / 'apply-status.json'
        override = override_settings(
            ENV_APPLY_REQUEST_FILE=self.request_path,
            ENV_APPLY_STATUS_FILE=self.status_path,
        )
        override.enable()
        self.addCleanup(override.disable)

    def _set_maintenance(self, enabled: bool):
        site = SiteConfiguration.get_instance()
        site.maintenance_mode = enabled
        site.save()

    def test_superuser_gets_apply_status_payload(self):
        self.client.force_login(self.superuser)
        self._set_maintenance(True)
        self.status_path.write_text(
            json.dumps({'status': 'ok', 'finished_at': '2026-11-10T12:00:05+00:00'}),
            encoding='utf-8',
        )

        response = self.client.get(self.status_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['apply_status']['state'], 'ok')
        self.assertFalse(data['apply_pending'])
        self.assertTrue(data['maintenance_mode'])
        self.assertIn('dev_simulator', data)

    def test_staff_cannot_access_apply_status(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.status_url)

        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_access_apply_status(self):
        response = self.client.get(self.status_url)

        self.assertEqual(response.status_code, 403)

    def test_apply_status_rejects_post(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.status_url)

        self.assertEqual(response.status_code, 405)

    def test_page_includes_restart_overlay_and_status_url(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertContains(response, 'id="env-apply-overlay"')
        self.assertContains(response, 'id="env-apply-submit"')
        self.assertContains(response, 'data-status-url="' + self.status_url + '"')
        self.assertContains(response, 'Aplicando cambios')
