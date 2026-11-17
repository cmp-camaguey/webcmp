"""Gate pre-despliegue: migraciones versionadas y configuracion valida.

Ejecuta los dos gates que antes vivian en deploy.sh como llamadas
separadas a manage.py. No toca la base ni archivos.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Verifica que el deploy puede continuar: migraciones y configuracion'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-dry-run',
            action='store_true',
            help='Solo ejecuta makemigrations --check --dry-run',
        )
        parser.add_argument(
            '--check-deploy',
            action='store_true',
            help='Solo ejecuta check --deploy',
        )

    def handle(self, *args, **options):
        run_makemigrations = not options.get('check_deploy')
        run_deploy = not options.get('check_dry_run')

        if not run_makemigrations and not run_deploy:
            return

        errors = []

        if run_makemigrations:
            errors.extend(self._run_makemigrations())

        if run_deploy:
            errors.extend(self._run_check_deploy())

        if errors:
            raise CommandError('deploy_check fallo:\n  ' + '\n  '.join(errors))

    def _run_makemigrations(self):
        """Ejecuta makemigrations --check --dry-run.

        Django usa sys.exit(2) cuando hay cambios sin migracion y
        sys.exit(1) para otros errores. call_command lo captura
        como SystemExit.
        """
        errors = []
        try:
            call_command(
                'makemigrations',
                check=True,
                dry_run=True,
                verbosity=1,
            )
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            if code != 0:
                errors.append(
                    'makemigrations --check: falta una migracion para un cambio de modelo. '
                    'Ejecuta `manage.py makemigrations` antes de desplegar.'
                )
        return errors

    def _run_check_deploy(self):
        """Ejecuta check --deploy --fail-level WARNING.

        Django levanta SystemCheckError (subclase de CommandError)
        cuando hay warnings o errores.
        """
        errors = []
        try:
            call_command(
                'check',
                deploy=True,
                fail_level='WARNING',
                verbosity=1,
            )
        except CommandError:
            errors.append('check --deploy: problemas de configuracion. El log de arriba dice cual.')
        return errors
