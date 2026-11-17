"""Aplicación de despliegue: migraciones, grupos de rol y estaticos.

Reemplaza las cuatro llamadas sueltas de `deploy.sh` por un unico comando
de negocio que corre como el usuario del sitio, no como root. Los pasos
se ejecutan en orden porque cada uno depende del anterior (los grupos
necesitan los permisos que `migrate` acaba de crear), y un fallo aborta
con el paso nombrado en lugar de un exit 1 anonimo.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Aplica el deploy: migrate, create_role_groups y collectstatic'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Imprime el plan sin ejecutar nada',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self.stdout.write('  migraciones: migrate --noinput, migrate --check')
            self.stdout.write('  grupos de rol: create_role_groups (idempotente)')
            self.stdout.write('  estaticos: collectstatic --no-input')
            return

        steps = [
            ('migrate', lambda: call_command('migrate', interactive=False)),
            ('migrate --check', lambda: call_command('migrate', check_unapplied=True)),
            ('create_role_groups', lambda: call_command('create_role_groups')),
            ('collectstatic', lambda: call_command('collectstatic', interactive=False)),
        ]

        for name, step in steps:
            try:
                step()
            except SystemExit as e:
                # `migrate --check` sale con codigo 1 si queda algo sin aplicar.
                code = e.code if isinstance(e.code, int) else 1
                if code != 0:
                    raise CommandError(
                        f'deploy_apply fallo en {name}: quedan migraciones sin aplicar en la base.'
                    ) from None
            except CommandError as e:
                raise CommandError(f'deploy_apply fallo en {name}: {e}') from None
