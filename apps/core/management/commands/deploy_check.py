"""Gate pre-despliegue: migraciones versionadas y configuracion valida.

Ejecuta los dos gates que antes vivian en deploy.sh como llamadas
separadas a manage.py. No toca la base ni archivos.

El gate de migraciones replica `makemigrations --check --dry-run`, pero
desregistra temporalmente los modelos definidos en modulos de test
(`apps/*/tests/...`) del app registry antes de correrlo. Sin eso, un
deploy corrido dentro de la suite (o con el registro sucio de tests)
fallaria por `SimpleFileModel`/`SoftDeleteFileModel`, que no estan en
las migraciones y no pueden gatear un despliegue. Es la misma fuente que
usa `apps.user_auth.roles.migrated_model_keys()`.
"""

from contextlib import contextmanager

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Verifica que el deploy puede continuar: migraciones y configuracion'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-dry-run',
            action='store_true',
            help='Solo verifica las migraciones (sin check --deploy)',
        )
        parser.add_argument(
            '--check-deploy',
            action='store_true',
            help='Solo ejecuta check --deploy',
        )

    def handle(self, *args, **options):
        run_migrations = not options.get('check_deploy')
        run_deploy = not options.get('check_dry_run')

        if not run_migrations and not run_deploy:
            return

        errors = []

        if run_migrations:
            errors.extend(self._run_makemigrations())

        if run_deploy:
            errors.extend(self._run_check_deploy())

        if errors:
            raise CommandError('deploy_check fallo:\n  ' + '\n  '.join(errors))

    @contextmanager
    def _without_test_models(self):
        """Quita del app registry los modelos definidos en modulos de test.

        `apps.all_models[app_label]` es el mismo dict que `AppConfig.models`.
        Se modifica in-place para que `ProjectState.from_apps` vea el cambio.
        """
        removed = {}
        for app_label, models in apps.all_models.items():
            to_remove = {
                name: model for name, model in models.items() if '.tests.' in model.__module__
            }
            if to_remove:
                removed[app_label] = to_remove
                for name in to_remove:
                    del models[name]
            apps.clear_cache()
        try:
            yield
        finally:
            for app_label, models_dict in removed.items():
                apps.all_models[app_label].update(models_dict)
            apps.clear_cache()

    def _run_makemigrations(self):
        """Gate de migraciones: `makemigrations --check --dry-run` sin modelos de test.

        Django sale con codigo 2 si hay cambios de modelo sin migracion,
        codigo 1 para otros errores. call_command los captura como SystemExit.
        """
        with self._without_test_models():
            try:
                call_command('makemigrations', check=True, dry_run=True, verbosity=1)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                if code != 0:
                    return [
                        'migraciones faltantes: un cambio de modelo no trae su '
                        'migracion. Ejecute `manage.py makemigrations` antes de '
                        'desplegar.'
                    ]
        return []

    def _run_check_deploy(self):
        """Ejecuta check --deploy --fail-level WARNING.

        Django levanta SystemCheckError (subclase de CommandError)
        cuando hay warnings o errores.
        """
        try:
            call_command('check', deploy=True, fail_level='WARNING', verbosity=1)
        except CommandError:
            return ['check --deploy: problemas de configuracion. El log de arriba dice cual.']
        return []
