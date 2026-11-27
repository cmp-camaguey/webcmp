"""Ejecutor de respaldo/restauración para desarrollo (change 040).

En producción, unidades systemd `.path` disparan `webcmp-deploy
--backup-manual` / `--restore-request` como root. En desarrollo no hay systemd,
así que este comando consume la misma petición y produce el mismo
estado/manifiesto que espera el panel.

Diferencias deliberadas respecto de producción:
- no para ni levanta `webcmp`/`webcmp-huey`;
- no usa `systemd-run`;
- no fuerza dueño root en los archivos.

La restauración sigue siendo destructiva: toma dump de seguridad y ejecuta
`pg_restore --clean --if-exists --single-transaction`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.dashboard.services import backup as backup_service


class Command(BaseCommand):
    help = (
        'Procesa peticiones de respaldo/restauración en desarrollo '
        '(mismo contrato de archivos que producción).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--watch',
            action='store_true',
            help='Sigue esperando peticiones (polling cada 2s).',
        )

    def handle(self, *args, **options):
        self.watch = options['watch']
        self.verbosity = options['verbosity']
        self._ensure_paths()

        if not self.watch:
            processed = self._run_once()
            if not processed and self.verbosity:
                self.stdout.write('No hay peticiones pendientes.')
            return

        self.stdout.write('Esperando peticiones de respaldo/restauración (Ctrl+C para salir)...')
        try:
            while True:
                self._run_once()
                self._sleep(2)
        except KeyboardInterrupt:
            self.stdout.write('\nDetenido.')

    def _sleep(self, seconds):
        import time

        time.sleep(seconds)

    def _ensure_paths(self):
        for path in (
            settings.DB_BACKUP_DIR,
            Path(settings.DB_BACKUP_MANIFEST_FILE).parent,
            Path(settings.DB_BACKUP_STATUS_FILE).parent,
        ):
            Path(path).mkdir(parents=True, exist_ok=True)

    def _run_once(self):
        restore = Path(settings.DB_RESTORE_REQUEST_FILE)
        backup = Path(settings.DB_BACKUP_REQUEST_FILE)
        # Restaurar primero: es la petición más delicada y la más rara.
        if restore.exists():
            self._handle_restore(restore)
            return True
        if backup.exists():
            self._handle_backup(backup)
            return True
        return False

    # --- Estado/manifiesto -------------------------------------------------

    def _write_json(self, path, payload):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f'{path.name}.tmp')
        with tmp.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.write('\n')
        os.replace(tmp, path)

    def _status(
        self,
        *,
        kind,
        status,
        message='',
        file=None,
        safety_file=None,
        requested_by='',
        started_at=None,
    ):
        now = datetime.now(UTC).isoformat()
        self._write_json(
            settings.DB_BACKUP_STATUS_FILE,
            {
                'kind': kind,
                'status': status,
                'message': message,
                'file': file,
                'safety_file': safety_file,
                'requested_by': requested_by,
                'started_at': started_at or now,
                'finished_at': None if status == 'running' else now,
            },
        )

    def _manifest(self):
        backup_dir = Path(settings.DB_BACKUP_DIR)
        entries = []
        if backup_dir.is_dir():
            for item in sorted(
                backup_dir.glob('*.dump'), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                entries.append(
                    {
                        'name': item.name,
                        'size': item.stat().st_size,
                        'created_at': datetime.fromtimestamp(
                            item.stat().st_mtime, tz=UTC
                        ).isoformat(),
                        'kind': self._kind(item.name),
                    }
                )
        self._write_json(
            settings.DB_BACKUP_MANIFEST_FILE,
            {
                'generated_at': datetime.now(UTC).isoformat(),
                'dir': str(backup_dir),
                'keep': int(settings.DB_BACKUP_KEEP),
                'backups': entries,
            },
        )

    @staticmethod
    def _kind(name):
        if name.endswith('-scheduled.dump'):
            return 'scheduled'
        if name.endswith('-manual.dump'):
            return 'manual'
        if name.endswith('-pre-restore.dump'):
            return 'pre-restore'
        if re.search(r'-to-[^.]+\.dump$', name):
            return 'pre-migrate'
        return 'unknown'

    # --- DB ----------------------------------------------------------------

    def _db_env(self):
        db = connection.settings_dict
        engine = str(db.get('ENGINE', ''))
        if 'postgresql' not in engine:
            raise CommandError(f'El respaldo solo soporta PostgreSQL (ENGINE={engine}).')
        env = dict(os.environ)
        env.update(
            {
                'PGHOST': str(db.get('HOST') or ''),
                'PGPORT': str(db.get('PORT') or ''),
                'PGUSER': str(db.get('USER') or ''),
                'PGPASSWORD': str(db.get('PASSWORD') or ''),
                'PGDATABASE': str(db.get('NAME') or ''),
            }
        )
        return env, str(db.get('NAME') or '')

    def _run_cmd(self, cmd, env):
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or '').strip()
            detail = detail[-800:] if detail else 'sin detalle'
            raise CommandError(detail)
        return result

    def _dump(self, dest, env, dbname):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        self._run_cmd(['pg_dump', '--format=custom', '--file', str(dest), dbname], env)

    def _restore(self, src, env, dbname):
        self._run_cmd(
            [
                'pg_restore',
                '--clean',
                '--if-exists',
                '--single-transaction',
                '--dbname',
                dbname,
                str(src),
            ],
            env,
        )

    def _prune(self):
        keep = int(settings.DB_BACKUP_KEEP)
        keep = max(1, keep)
        dumps = sorted(
            Path(settings.DB_BACKUP_DIR).glob('*.dump'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in dumps[keep:]:
            old.unlink(missing_ok=True)

    # --- Peticiones --------------------------------------------------------

    def _read_request(self, path):
        try:
            with Path(path).open(encoding='utf-8') as handle:
                data = json.load(handle)
        except OSError, ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _handle_backup(self, request_path):
        raw = self._read_request(request_path)
        requested_by = str(raw.get('requested_by') or '').strip()
        started_at = datetime.now(UTC).isoformat()
        request_path.unlink(missing_ok=True)
        self._status(
            kind='backup',
            status='running',
            message='Respaldo en curso (dev).',
            requested_by=requested_by,
            started_at=started_at,
        )

        try:
            env, dbname = self._db_env()
            stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
            name = f'webcmp-{stamp}-manual.dump'
            dest = Path(settings.DB_BACKUP_DIR) / name
            self._dump(dest, env, dbname)
            self._prune()
            self._manifest()
            self._status(
                kind='backup',
                status='ok',
                message='Respaldo completado (dev).',
                file=name,
                requested_by=requested_by,
                started_at=started_at,
            )
            if self.verbosity:
                self.stdout.write(self.style.SUCCESS(f'Respaldo creado: {name}'))
        except Exception as error:
            self._manifest()
            self._status(
                kind='backup',
                status='failed',
                message='El respaldo fallo. Revise la consola.',
                requested_by=requested_by,
                started_at=started_at,
            )
            self.stderr.write(self.style.ERROR(f'Respaldo fallido: {error}'))

    def _handle_restore(self, request_path):
        raw = self._read_request(request_path)
        requested_by = str(raw.get('requested_by') or '').strip()
        name = raw.get('file')
        started_at = datetime.now(UTC).isoformat()
        request_path.unlink(missing_ok=True)

        if not backup_service.valid_backup_name(name):
            self._status(
                kind='restore',
                status='failed',
                message='El respaldo pedido no es valido.',
                requested_by=requested_by,
                started_at=started_at,
            )
            self._manifest()
            self.stderr.write(self.style.ERROR(f'Nombre de respaldo inválido: {name!r}'))
            return

        src = Path(settings.DB_BACKUP_DIR) / name
        if not src.is_file():
            self._status(
                kind='restore',
                status='failed',
                message='El respaldo pedido no existe.',
                requested_by=requested_by,
                started_at=started_at,
            )
            self._manifest()
            self.stderr.write(self.style.ERROR(f'No existe: {src}'))
            return

        self._status(
            kind='restore',
            status='running',
            message='Restauración en curso (dev): no se detienen servicios.',
            requested_by=requested_by,
            started_at=started_at,
        )

        safety_name = None
        try:
            env, dbname = self._db_env()
            stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
            safety_name = f'webcmp-{stamp}-pre-restore.dump'
            safety = Path(settings.DB_BACKUP_DIR) / safety_name
            self._dump(safety, env, dbname)

            self._restore(src, env, dbname)
            self._manifest()
            self._status(
                kind='restore',
                status='ok',
                message='Restauración completada (dev).',
                file=name,
                safety_file=safety_name,
                requested_by=requested_by,
                started_at=started_at,
            )
            if self.verbosity:
                self.stdout.write(
                    self.style.SUCCESS(f'Restaurado: {name} (seguridad: {safety_name})')
                )
        except Exception as error:
            self._manifest()
            self._status(
                kind='restore',
                status='failed',
                message='La restauración falló. El respaldo de seguridad queda disponible.',
                file=name,
                safety_file=safety_name,
                requested_by=requested_by,
                started_at=started_at,
            )
            self.stderr.write(self.style.ERROR(f'Restauración fallida: {error}'))
