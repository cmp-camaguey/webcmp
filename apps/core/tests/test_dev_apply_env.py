"""Tests del simulador del ejecutor de entorno para desarrollo."""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.core.env_apply import PENDING_GRACE_SECONDS, apply_status, pending_request


class DevApplyEnvCommandTests(SimpleTestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir, ignore_errors=True)
        self.request = Path(self.tempdir) / 'apply-request'
        self.status = Path(self.tempdir) / 'apply-status.json'
        self.env = Path(self.tempdir) / '.env'
        self.env.write_text('EMAIL_HOST=smtp.viejo.cu\n', encoding='utf-8')
        settings_override = override_settings(
            ENV_APPLY_REQUEST_FILE=self.request,
            ENV_APPLY_STATUS_FILE=self.status,
            ENV_FILE_PATH=self.env,
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def _run(self):
        call_command('dev_apply_env', verbosity=0)

    def test_consumes_the_request(self):
        self.request.write_text(json.dumps({'requested_by': 'root'}), encoding='utf-8')

        self._run()

        self.assertFalse(self.request.exists())

    def test_publishes_ok_with_the_requester(self):
        self.request.write_text(json.dumps({'requested_by': 'root'}), encoding='utf-8')

        self._run()

        status = apply_status(self.status)
        self.assertEqual(status['state'], 'ok')
        self.assertIn('root', status['text'])

    def test_clears_the_pending_warning(self):
        self.request.write_text(json.dumps({'requested_by': 'root'}), encoding='utf-8')
        old = time.time() - PENDING_GRACE_SECONDS - 1
        os.utime(self.request, (old, old))
        self.assertIsNotNone(pending_request(self.request))

        self._run()

        self.assertIsNone(pending_request(self.request))

    def test_without_a_request_still_publishes_ok(self):
        self._run()

        self.assertEqual(apply_status(self.status)['state'], 'ok')

    def test_does_not_touch_the_env_file(self):
        self.request.write_text(json.dumps({'requested_by': 'root'}), encoding='utf-8')

        self._run()

        self.assertEqual(self.env.read_text(encoding='utf-8'), 'EMAIL_HOST=smtp.viejo.cu\n')

    def test_broken_request_json_is_still_consumed(self):
        self.request.write_text('{json roto', encoding='utf-8')

        self._run()

        self.assertFalse(self.request.exists())
        self.assertEqual(apply_status(self.status)['state'], 'ok')
