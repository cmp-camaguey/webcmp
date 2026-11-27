"""Respaldo y restauracion de la base desde el panel (change 040).

El contrato que se prueba es el de siempre en este proyecto: el proceso web no
tiene privilegios y no toca el dump. Escribe una peticion, una unidad systemd
la recoge y un ejecutor root deja el estado y el manifiesto en archivos que el
panel solo lee.

Por eso las pruebas no abren PostgreSQL: verifican la frontera (peticiones,
validacion de nombres, lectura tolerante de archivos escritos por otro usuario)
y no el `pg_dump`, que se prueba en `deploy/tests/`.
"""

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import SiteConfiguration
from apps.dashboard.services import backup as backup_service

BACKUP_NAME = 'webcmp-20261127T031500Z-scheduled.dump'


def _superuser(username='admin'):
    return User.objects.create_superuser(
        username,
        f'{username}@example.com',
        'pass',
        first_name='Admin',
        last_name='Super',
    )


def _user(username='operador'):
    return User.objects.create_user(
        username,
        f'{username}@example.com',
        'pass',
        first_name='Operador',
        last_name='Comun',
    )


class BackupFilesMixin:
    """Aisla los cuatro archivos y desactiva el modo mantenimiento."""

    def setUp(self):
        SiteConfiguration.objects.update_or_create(pk=1, defaults={'maintenance_mode': False})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmpdir = tmp.name

        self.backup_request = os.path.join(self.tmpdir, 'backup-request')
        self.restore_request = os.path.join(self.tmpdir, 'restore-request')
        self.status_file = os.path.join(self.tmpdir, 'backup-status.json')
        self.manifest_file = os.path.join(self.tmpdir, 'backup-manifest.json')
        self.download_request = os.path.join(self.tmpdir, 'download-request')
        self.download_status_file = os.path.join(self.tmpdir, 'download-status.json')
        self.download_staging = os.path.join(self.tmpdir, 'downloads')
        self.upload_staging = os.path.join(self.tmpdir, 'uploads')
        os.makedirs(self.download_staging, exist_ok=True)
        os.makedirs(self.upload_staging, exist_ok=True)

        override = override_settings(
            DB_BACKUP_REQUEST_FILE=self.backup_request,
            DB_RESTORE_REQUEST_FILE=self.restore_request,
            DB_BACKUP_STATUS_FILE=self.status_file,
            DB_BACKUP_MANIFEST_FILE=self.manifest_file,
            DB_BACKUP_DIR=os.path.join(self.tmpdir, 'db'),
            DB_BACKUP_KEEP=10,
            DB_DOWNLOAD_REQUEST_FILE=self.download_request,
            DB_DOWNLOAD_STATUS_FILE=self.download_status_file,
            DB_DOWNLOAD_STAGING_DIR=self.download_staging,
            DB_UPLOAD_STAGING_DIR=self.upload_staging,
            DB_DOWNLOAD_TTL_SECONDS=1800,
            DB_UPLOAD_MAX_SIZE=10 * 1024 * 1024,
        )
        override.enable()
        self.addCleanup(override.disable)

    def write_manifest(self, backups, **extra):
        payload = {
            'generated_at': '2026-11-27T03:15:04-05:00',
            'dir': '/var/backups/webcmp/db',
            'keep': 10,
            'backups': backups,
            **extra,
        }
        Path(self.manifest_file).write_text(json.dumps(payload), encoding='utf-8')

    def write_status(self, **payload):
        Path(self.status_file).write_text(json.dumps(payload), encoding='utf-8')


class ValidNameTests(TestCase):
    def test_accepts_dump_names(self):
        for name in (
            'webcmp-20261127T031500Z-scheduled.dump',
            'webcmp-20261127T031500Z-pre-restore.dump',
            'a.dump',
            'A_b-c.dump',
        ):
            with self.subTest(name=name):
                self.assertTrue(backup_service.valid_backup_name(name))

    def test_rejects_traversal_and_absolute(self):
        for name in (
            '',
            '../etc/passwd.dump',
            '/var/backups/webcmp/db/a.dump',
            'sub/a.dump',
            'a.dump/../b.dump',
            '..',
        ):
            with self.subTest(name=name):
                self.assertFalse(backup_service.valid_backup_name(name))

    def test_rejects_non_dump_and_odd_names(self):
        for name in ('a.sql', 'a.dump.bak', '-a.dump', 'a b.dump', 'a.dump\x00'):
            with self.subTest(name=name):
                self.assertFalse(backup_service.valid_backup_name(name))


class RequestTests(BackupFilesMixin, TestCase):
    def test_request_backup_writes_json(self):
        user = _user()
        payload = backup_service.request_backup(self.backup_request, user)

        self.assertTrue(Path(self.backup_request).exists())
        stored = json.loads(Path(self.backup_request).read_text(encoding='utf-8'))
        self.assertEqual(stored['requested_by'], 'operador')
        self.assertEqual(stored, payload)
        self.assertIn('requested_at', stored)

    def test_request_backup_refuses_a_second(self):
        user = _user()
        backup_service.request_backup(self.backup_request, user)
        with self.assertRaises(backup_service.BackupRequestPendingError):
            backup_service.request_backup(self.backup_request, user)

    def test_request_restore_writes_filename(self):
        user = _user()
        backup_service.request_restore(self.restore_request, user, BACKUP_NAME)
        stored = json.loads(Path(self.restore_request).read_text(encoding='utf-8'))
        self.assertEqual(stored['file'], BACKUP_NAME)
        self.assertEqual(stored['requested_by'], 'operador')

    def test_pending_request_is_quiet_right_after_creation(self):
        backup_service.request_backup(self.backup_request, _user())
        self.assertIsNone(backup_service.pending_request(self.backup_request))

    def test_pending_request_warns_when_nobody_picked_it_up(self):
        backup_service.request_backup(self.backup_request, _user())
        old = (datetime.now(UTC) - timedelta(minutes=5)).timestamp()
        os.utime(self.backup_request, (old, old))

        pending = backup_service.pending_request(self.backup_request)
        self.assertIsNotNone(pending)
        self.assertEqual(pending['tone'], 'warning')
        self.assertIn('operador', pending['text'])

    def test_can_request_checks_the_directory(self):
        self.assertTrue(backup_service.can_request(self.backup_request))
        self.assertFalse(backup_service.can_request(os.path.join(self.tmpdir, 'nope', 'request')))


class StatusTests(BackupFilesMixin, TestCase):
    def test_parses_running(self):
        self.write_status(
            kind='backup',
            status='running',
            message='Respaldo en curso.',
            started_at=datetime.now(UTC).isoformat(),
            finished_at=None,
        )
        status = backup_service.backup_status(self.status_file)
        self.assertEqual(status['state'], 'running')
        self.assertEqual(status['kind'], 'backup')
        self.assertEqual(status['tone'], 'info')

    def test_parses_ok_with_file(self):
        self.write_status(
            kind='backup',
            status='ok',
            message='Respaldo completado.',
            file=BACKUP_NAME,
            started_at=datetime.now(UTC).isoformat(),
            finished_at=datetime.now(UTC).isoformat(),
        )
        status = backup_service.backup_status(self.status_file)
        self.assertEqual(status['state'], 'ok')
        self.assertEqual(status['file'], BACKUP_NAME)
        self.assertEqual(status['tone'], 'success')

    def test_marks_stale_running(self):
        self.write_status(
            kind='restore',
            status='running',
            started_at=(datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        )
        status = backup_service.backup_status(self.status_file)
        self.assertEqual(status['state'], 'stale')
        self.assertEqual(status['tone'], 'warning')

    def test_ignores_malformed_status(self):
        Path(self.status_file).write_text('{no json', encoding='utf-8')
        self.assertIsNone(backup_service.backup_status(self.status_file))

        Path(self.status_file).write_text(json.dumps({'status': 'inventado'}), encoding='utf-8')
        self.assertIsNone(backup_service.backup_status(self.status_file))

    def test_missing_status_is_none(self):
        self.assertIsNone(backup_service.backup_status(self.status_file))

    def test_is_busy(self):
        self.assertTrue(backup_service.is_busy({'state': 'running'}))
        # `stale` no bloquea: si el estado quedo colgado, el operador tiene que
        # poder reintentar sin entrar por SSH.
        self.assertFalse(backup_service.is_busy({'state': 'stale'}))
        self.assertFalse(backup_service.is_busy({'state': 'ok'}))
        self.assertFalse(backup_service.is_busy(None))


class ManifestTests(BackupFilesMixin, TestCase):
    def test_reads_valid_entries(self):
        self.write_manifest(
            [
                {
                    'name': BACKUP_NAME,
                    'size': 2048,
                    'created_at': '2026-11-27T03:15:04Z',
                    'kind': 'scheduled',
                }
            ]
        )
        manifest = backup_service.backup_manifest(self.manifest_file)
        self.assertEqual(len(manifest['backups']), 1)
        self.assertEqual(manifest['backups'][0]['name'], BACKUP_NAME)
        self.assertEqual(manifest['backups'][0]['size'], 2048)
        self.assertEqual(manifest['keep'], 10)

    def test_drops_invalid_entries(self):
        self.write_manifest(
            [
                {'name': BACKUP_NAME, 'size': 1, 'kind': 'manual'},
                {'name': '../evil.dump', 'size': 1, 'kind': 'manual'},
                {'name': 'no-es-dump', 'size': 1, 'kind': 'manual'},
                {'name': BACKUP_NAME, 'size': 'grande', 'kind': 'manual'},
                'texto',
                None,
            ]
        )
        manifest = backup_service.backup_manifest(self.manifest_file)
        self.assertEqual([b['name'] for b in manifest['backups']], [BACKUP_NAME])

    def test_missing_manifest_is_empty(self):
        manifest = backup_service.backup_manifest(self.manifest_file)
        self.assertEqual(manifest['backups'], [])

    def test_broken_manifest_is_empty(self):
        Path(self.manifest_file).write_text('{roto', encoding='utf-8')
        self.assertEqual(backup_service.backup_manifest(self.manifest_file)['backups'], [])


class DatabaseViewTests(BackupFilesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = _superuser()
        self.regular = _user()

    def test_page_requires_login(self):
        response = self.client.get(reverse('dashboard:database'))
        self.assertEqual(response.status_code, 302)

    def test_page_forbidden_for_non_superuser(self):
        self.client.force_login(self.regular)
        response = self.client.get(reverse('dashboard:database'))
        self.assertEqual(response.status_code, 403)

    def test_page_ok_for_superuser(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:database'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Respaldo de BD')

    def test_data_returns_manifest_and_status(self):
        self.write_manifest(
            [
                {
                    'name': BACKUP_NAME,
                    'size': 10,
                    'created_at': '2026-11-27T03:15:04Z',
                    'kind': 'scheduled',
                }
            ]
        )
        self.write_status(
            kind='backup',
            status='ok',
            started_at=datetime.now(UTC).isoformat(),
            finished_at=datetime.now(UTC).isoformat(),
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:database_data'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['manifest']['backups'][0]['name'], BACKUP_NAME)
        self.assertEqual(payload['status']['state'], 'ok')
        self.assertTrue(payload['can_request'])

    def test_data_forbidden_for_non_superuser(self):
        self.client.force_login(self.regular)
        response = self.client.get(reverse('dashboard:database_data'))
        self.assertEqual(response.status_code, 403)

    def test_backup_post_creates_request(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('dashboard:database_backup'))
        self.assertEqual(response.status_code, 202)
        self.assertTrue(Path(self.backup_request).exists())

    def test_backup_post_conflict(self):
        self.client.force_login(self.admin)
        Path(self.backup_request).write_text('{}', encoding='utf-8')
        response = self.client.post(reverse('dashboard:database_backup'))
        self.assertEqual(response.status_code, 409)

    def test_restore_post_requires_confirmation(self):
        self.write_manifest([{'name': BACKUP_NAME, 'size': 1, 'kind': 'manual'}])
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:database_restore'),
            data=json.dumps({'filename': BACKUP_NAME, 'confirm': 'si'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Path(self.restore_request).exists())

    def test_restore_post_rejects_unknown_file(self):
        self.write_manifest([{'name': BACKUP_NAME, 'size': 1, 'kind': 'manual'}])
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:database_restore'),
            data=json.dumps(
                {'filename': '../otro.dump', 'confirm': backup_service.RESTORE_CONFIRMATION}
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Path(self.restore_request).exists())

    def test_restore_post_accepts_manifest_file(self):
        self.write_manifest([{'name': BACKUP_NAME, 'size': 1, 'kind': 'manual'}])
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:database_restore'),
            data=json.dumps(
                {'filename': BACKUP_NAME, 'confirm': backup_service.RESTORE_CONFIRMATION}
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 202)
        stored = json.loads(Path(self.restore_request).read_text(encoding='utf-8'))
        self.assertEqual(stored['file'], BACKUP_NAME)

    def test_restore_post_rejects_while_running(self):
        self.write_manifest([{'name': BACKUP_NAME, 'size': 1, 'kind': 'manual'}])
        self.write_status(
            kind='restore',
            status='running',
            started_at=datetime.now(UTC).isoformat(),
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:database_restore'),
            data=json.dumps(
                {'filename': BACKUP_NAME, 'confirm': backup_service.RESTORE_CONFIRMATION}
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Path(self.restore_request).exists())


class DatabaseDownloadUploadTests(BackupFilesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = _superuser()
        self.regular = _user()

    def _write_download_status(self, **payload):
        Path(self.download_status_file).write_text(json.dumps(payload), encoding='utf-8')

    def test_download_request_requires_confirmation(self):
        self.write_manifest([{'name': BACKUP_NAME, 'size': 1, 'kind': 'manual'}])
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:database_download_request'),
            data=json.dumps({'filename': BACKUP_NAME, 'confirm': 'no'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Path(self.download_request).exists())

    def test_download_request_creates_file(self):
        self.write_manifest([{'name': BACKUP_NAME, 'size': 1, 'kind': 'manual'}])
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('dashboard:database_download_request'),
            data=json.dumps(
                {'filename': BACKUP_NAME, 'confirm': backup_service.DOWNLOAD_CONFIRMATION}
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 202)
        stored = json.loads(Path(self.download_request).read_text(encoding='utf-8'))
        self.assertEqual(stored['file'], BACKUP_NAME)

    def test_download_request_forbidden_for_non_superuser(self):
        self.client.force_login(self.regular)
        response = self.client.post(
            reverse('dashboard:database_download_request'),
            data=json.dumps(
                {'filename': BACKUP_NAME, 'confirm': backup_service.DOWNLOAD_CONFIRMATION}
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_download_serves_staged_file_and_consumes(self):
        token = 'a' * 64
        staged = Path(self.download_staging) / f'{token}.dump'
        staged.write_bytes(b'dump-content')
        self._write_download_status(
            status='ok',
            file=BACKUP_NAME,
            download_name=BACKUP_NAME,
            token=token,
            requested_by='admin',
            started_at=datetime.now(UTC).isoformat(),
            finished_at=datetime.now(UTC).isoformat(),
            expires_at='2099-01-01T00:00:00+00:00',
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:database_download', args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'dump-content')
        self.assertFalse(staged.exists())

    def test_download_rejects_invalid_token(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard:database_download', args=['bad']))
        self.assertEqual(response.status_code, 404)

    def test_upload_requires_confirmation(self):
        self.client.force_login(self.admin)
        f = SimpleUploadedFile('test.dump', b'data')
        response = self.client.post(
            reverse('dashboard:database_upload'), {'file': f, 'confirm': 'no'}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Path(self.restore_request).exists())

    def test_upload_rejects_non_dump(self):
        self.client.force_login(self.admin)
        f = SimpleUploadedFile('test.sql', b'data')
        response = self.client.post(
            reverse('dashboard:database_upload'),
            {'file': f, 'confirm': backup_service.RESTORE_CONFIRMATION},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_creates_restore_request(self):
        self.client.force_login(self.admin)
        f = SimpleUploadedFile('backup.dump', b'PGDMP-test')
        response = self.client.post(
            reverse('dashboard:database_upload'),
            {'file': f, 'confirm': backup_service.RESTORE_CONFIRMATION},
        )
        self.assertEqual(response.status_code, 202)
        stored = json.loads(Path(self.restore_request).read_text(encoding='utf-8'))
        self.assertEqual(stored['source'], 'upload')
        self.assertTrue(stored['file'].startswith('upload-'))
        staged = Path(self.upload_staging) / stored['file']
        self.assertTrue(staged.exists())
