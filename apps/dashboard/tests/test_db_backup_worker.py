import json
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


def _manifest_entry(name, kind='manual'):
    return {'name': name, 'size': 10, 'created_at': '2026-11-27T00:00:00+00:00', 'kind': kind}


class DbBackupWorkerTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.dir = self.root / 'db'
        self.dir.mkdir()
        self.request = self.root / 'backup-request'
        self.restore = self.root / 'restore-request'
        self.status = self.root / 'backup-status.json'
        self.manifest = self.root / 'backup-manifest.json'
        self.override = override_settings(
            DB_BACKUP_DIR=str(self.dir),
            DB_BACKUP_KEEP=10,
            DB_BACKUP_REQUEST_FILE=str(self.request),
            DB_RESTORE_REQUEST_FILE=str(self.restore),
            DB_BACKUP_STATUS_FILE=str(self.status),
            DB_BACKUP_MANIFEST_FILE=str(self.manifest),
        )
        self.override.enable()
        self.addCleanup(self.override.disable)

    def _read(self, path):
        return json.loads(Path(path).read_text(encoding='utf-8'))

    def test_no_request_is_noop(self):
        call_command('db_backup_worker', verbosity=0)
        self.assertFalse(self.status.exists())

    def test_backup_request_creates_dump_and_status(self):
        self.request.write_text(json.dumps({'requested_by': 'admin'}), encoding='utf-8')

        def fake_dump(cmd, env, capture_output=True, text=True):
            # pg_dump --format=custom --file <dest> <dbname>
            Path(cmd[3]).write_bytes(b'dump')

            class R:
                returncode = 0
                stdout = ''
                stderr = ''

            return R()

        with (
            mock.patch(
                'apps.dashboard.management.commands.db_backup_worker.Command._db_env',
                return_value=({'PGHOST': ''}, 'webcmp'),
            ),
            mock.patch('subprocess.run', side_effect=fake_dump),
        ):
            call_command('db_backup_worker', verbosity=0)

        self.assertFalse(self.request.exists())
        status = self._read(self.status)
        self.assertEqual(status['kind'], 'backup')
        self.assertEqual(status['status'], 'ok')
        self.assertEqual(status['requested_by'], 'admin')
        self.assertTrue(status['file'].endswith('-manual.dump'))

        manifest = self._read(self.manifest)
        self.assertEqual(len(manifest['backups']), 1)
        self.assertEqual(manifest['backups'][0]['name'], status['file'])

    def test_restore_request_takes_safety_dump_and_restores(self):
        dump = self.dir / 'webcmp-20261127T000000Z-manual.dump'
        dump.write_bytes(b'old')
        self.restore.write_text(
            json.dumps({'requested_by': 'admin', 'file': dump.name}), encoding='utf-8'
        )

        calls = []

        def fake_run(cmd, env, capture_output=True, text=True):
            calls.append(cmd[0])
            if cmd[0] == 'pg_dump':
                Path(cmd[3]).write_bytes(b'safety')

            class R:
                returncode = 0
                stdout = ''
                stderr = ''

            return R()

        with (
            mock.patch(
                'apps.dashboard.management.commands.db_backup_worker.Command._db_env',
                return_value=({'PGHOST': ''}, 'webcmp'),
            ),
            mock.patch('subprocess.run', side_effect=fake_run),
        ):
            call_command('db_backup_worker', verbosity=0)

        self.assertFalse(self.restore.exists())
        self.assertEqual(calls, ['pg_dump', 'pg_restore'])
        status = self._read(self.status)
        self.assertEqual(status['kind'], 'restore')
        self.assertEqual(status['status'], 'ok')
        self.assertEqual(status['file'], dump.name)
        self.assertTrue(status['safety_file'].endswith('-pre-restore.dump'))

    def test_invalid_restore_name_fails_closed(self):
        self.restore.write_text(
            json.dumps({'requested_by': 'admin', 'file': '../evil.dump'}), encoding='utf-8'
        )
        call_command('db_backup_worker', verbosity=0)
        status = self._read(self.status)
        self.assertEqual(status['status'], 'failed')
        self.assertEqual(status['kind'], 'restore')

    def test_failed_backup_marks_failed(self):
        self.request.write_text(json.dumps({'requested_by': 'admin'}), encoding='utf-8')

        class R:
            returncode = 1
            stdout = ''
            stderr = 'boom'

        with (
            mock.patch(
                'apps.dashboard.management.commands.db_backup_worker.Command._db_env',
                return_value=({'PGHOST': ''}, 'webcmp'),
            ),
            mock.patch('subprocess.run', return_value=R()),
        ):
            call_command('db_backup_worker', verbosity=0)

        status = self._read(self.status)
        self.assertEqual(status['status'], 'failed')
        self.assertEqual(status['kind'], 'backup')
