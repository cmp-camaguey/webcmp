"""Pruebas de los comandos deploy_check y deploy_apply."""

import io
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


class DeployCheckTests(TestCase):
    """deploy_check ejecuta los dos gates y falla con mensaje nombrado."""

    @override_settings(
        DEBUG=False,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    def test_deploy_check_clean(self):
        """Sin cambios de modelo y con configuracion valida, el comando pasa."""
        # El arbol ya esta limpio (las migraciones estan versionadas) y
        # los warnings de seguridad estan silenciados con settings de prod.
        call_command('deploy_check')  # no lanza

    def test_deploy_check_only_makemigrations(self):
        """--check-dry-run ejecuta solo makemigrations --check."""
        call_command('deploy_check', check_dry_run=True)  # no lanza

    @override_settings(
        DEBUG=False,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    def test_deploy_check_only_deploy(self):
        """--check-deploy ejecuta solo check --deploy."""
        call_command('deploy_check', check_deploy=True)  # no lanza

    @patch('django.core.management.commands.makemigrations.Command.handle')
    def test_deploy_check_makemigrations_falla(self, mock_handle):
        """Si makemigrations --check falla, el error nombra ese gate."""

        def _side_effect(*args, **options):
            raise SystemExit(2)

        mock_handle.side_effect = _side_effect
        with self.assertRaisesRegex(CommandError, 'makemigrations --check'):
            call_command('deploy_check')

    @patch('django.core.management.commands.check.Command.handle')
    def test_deploy_check_check_deploy_falla(self, mock_handle):
        """Si check --deploy falla, el error nombra ese gate."""

        def _side_effect(*args, **options):
            raise CommandError('problema de configuracion')

        mock_handle.side_effect = _side_effect
        with self.assertRaisesRegex(CommandError, 'check --deploy'):
            call_command('deploy_check')


class DeployApplyTests(TestCase):
    """deploy_apply ejecuta los cuatro pasos en orden y aborta en el primero que falla."""

    def test_deploy_apply_dry_run(self):
        """--dry-run imprime el plan sin ejecutar."""
        out = io.StringIO()
        call_command('deploy_apply', dry_run=True, stdout=out)
        output = out.getvalue()
        self.assertIn('migraciones', output)
        self.assertIn('grupos de rol', output)
        self.assertIn('estaticos', output)

    @patch('apps.core.management.commands.deploy_apply.call_command')
    def test_deploy_apply_orden(self, mock_call):
        """Los pasos se ejecutan en el orden especificado."""
        call_command('deploy_apply')
        calls = [c[0][0] for c in mock_call.call_args_list]
        self.assertEqual(
            calls,
            ['migrate', 'migrate', 'create_role_groups', 'collectstatic'],
        )

    @patch('apps.core.management.commands.deploy_apply.call_command')
    def test_deploy_apply_migrate_check_falla(self, mock_call):
        """Si migrate --check falla, el error nombra ese paso."""

        def _side_effect(cmd, *args, **kwargs):
            if cmd == 'migrate' and kwargs.get('check_unapplied'):
                raise SystemExit(1)
            return None

        mock_call.side_effect = _side_effect
        with self.assertRaisesRegex(CommandError, 'migrate --check'):
            call_command('deploy_apply')

    @patch('apps.core.management.commands.deploy_apply.call_command')
    def test_deploy_apply_create_role_groups_falla(self, mock_call):
        """Si create_role_groups falla, el error nombra ese paso."""

        def _side_effect(cmd, *args, **kwargs):
            if cmd == 'create_role_groups':
                raise CommandError('falta un permiso')
            return None

        mock_call.side_effect = _side_effect
        with self.assertRaisesRegex(CommandError, 'create_role_groups'):
            call_command('deploy_apply')
