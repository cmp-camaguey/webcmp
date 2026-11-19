"""Simula en desarrollo el ejecutor root que reinicia los servicios.

En producción, `webcmp-apply.path` vigila `ENV_APPLY_REQUEST_FILE`: un script
root consume la petición, reinicia gunicorn/huey y publica el resultado en
`ENV_APPLY_STATUS_FILE`. En desarrollo no hay systemd, así que esa petición
queda en disco y el panel muestra «reinicio pendiente» para siempre.

Este comando hace la parte que el panel puede observar: consume la petición y
publica un desenlace `ok`. No reinicia nada. Cambiar el `.env` no modifica un
proceso ya arrancado: hay que reiniciar `runserver`/gunicorn a mano, y además
la variable no debe estar exportada en el entorno, porque `load_dotenv` no
sobrescribe lo que ya existe.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.env_apply import _read_json


class Command(BaseCommand):
    help = 'Simula el ejecutor de reinicio en desarrollo: consume la petición y publica estado ok'

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        request_path = Path(settings.ENV_APPLY_REQUEST_FILE)
        status_path = Path(settings.ENV_APPLY_STATUS_FILE)

        raw = _read_json(request_path)
        requested_by = str((raw or {}).get('requested_by') or '').strip()
        if request_path.exists():
            try:
                request_path.unlink()
            except OSError as error:
                raise CommandError(f'No se pudo consumir {request_path}: {error}') from error
            if verbosity:
                self.stdout.write(f'Petición consumida de {request_path}.')
        elif verbosity:
            self.stdout.write(f'No había petición pendiente en {request_path}.')

        self._write_ok(status_path, requested_by)
        if not verbosity:
            return
        self.stdout.write(f'Estado publicado en {status_path}.')
        self.stdout.write(
            self.style.WARNING(
                'El .env ya está leído por el proceso en marcha: reinicie '
                'runserver/gunicorn para que el cambio tenga efecto. Si la '
                'variable está exportada en el entorno, load_dotenv no la '
                'sobrescribe: quítela del entorno antes de reiniciar.'
            )
        )

    @staticmethod
    def _write_ok(path: Path, requested_by: str) -> None:
        """Publica el resultado con reemplazo atómico, como `write_status` del ejecutor."""
        now = datetime.now(UTC).isoformat()
        payload = {
            'status': 'ok',
            'requested_by': requested_by,
            'started_at': now,
            'finished_at': now,
            'error': '',
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f'{path.name}.tmp')
        try:
            with temporary.open('w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False)
                handle.write('\n')
            os.chmod(temporary, 0o644)
            os.replace(temporary, path)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise CommandError(f'No se pudo escribir {path}: {error}') from error
