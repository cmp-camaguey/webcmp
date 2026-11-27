"""Respaldo, restauracion, descarga y subida de la base (040/041).

El proceso web no ejecuta pg_dump/pg_restore ni lee DB_BACKUP_DIR. Escribe
peticiones que recogen unidades systemd y lee estado/manifiesto escritos por el
ejecutor root. La descarga sirve solo staging temporal; la subida se guarda en
staging y el ejecutor la valida antes de moverla a DB_BACKUP_DIR.
"""

import json
import logging
import os
from pathlib import Path

from django.conf import settings
from django.contrib.admin.models import CHANGE
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.utils.encoding import smart_str
from django.views.generic import TemplateView, View

from apps.core.utils import log_action
from apps.dashboard.services import backup as backup_service

logger = logging.getLogger(__name__)


class DatabaseBackupView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'pages/dashboard/database.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'title': 'Respaldo de BD',
                'parent': 'Sistema',
                'segment': 'database_backup',
                'data_url': reverse('dashboard:database_data'),
                'backup_url': reverse('dashboard:database_backup'),
                'restore_url': reverse('dashboard:database_restore'),
                'download_request_url': reverse('dashboard:database_download_request'),
                'upload_url': reverse('dashboard:database_upload'),
                'confirmation': backup_service.RESTORE_CONFIRMATION,
                'download_confirmation': backup_service.DOWNLOAD_CONFIRMATION,
                'upload_max_size': settings.DB_UPLOAD_MAX_SIZE,
            }
        )
        return context


class DatabaseBackupDataView(LoginRequiredMixin, UserPassesTestMixin, View):
    raise_exception = True
    http_method_names = ['get']

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, *args, **kwargs):
        download = backup_service.download_status(settings.DB_DOWNLOAD_STATUS_FILE)
        if download and download.get('state') == 'ok' and download.get('token'):
            download['url'] = reverse('dashboard:database_download', args=[download['token']])
        return JsonResponse(
            {
                'status': backup_service.backup_status(settings.DB_BACKUP_STATUS_FILE),
                'manifest': backup_service.backup_manifest(settings.DB_BACKUP_MANIFEST_FILE),
                'download': download,
                'pending_backup': backup_service.pending_request(
                    settings.DB_BACKUP_REQUEST_FILE,
                    label='respaldo',
                    unit='webcmp-backup.path',
                ),
                'pending_restore': backup_service.pending_request(
                    settings.DB_RESTORE_REQUEST_FILE,
                    label='restauracion',
                    unit='webcmp-restore.path',
                ),
                'pending_download': backup_service.pending_request(
                    settings.DB_DOWNLOAD_REQUEST_FILE,
                    label='descarga',
                    unit='webcmp-download.path',
                ),
                'can_request': backup_service.can_request(settings.DB_BACKUP_REQUEST_FILE),
            }
        )


class DatabaseBackupRequestView(LoginRequiredMixin, UserPassesTestMixin, View):
    raise_exception = True
    http_method_names = ['post']

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        status = backup_service.backup_status(settings.DB_BACKUP_STATUS_FILE)
        if backup_service.is_busy(status):
            return JsonResponse(
                {'ok': False, 'reason': 'Ya hay una operacion en curso.'}, status=409
            )

        try:
            payload = backup_service.request_backup(settings.DB_BACKUP_REQUEST_FILE, request.user)
        except backup_service.BackupRequestPendingError:
            return JsonResponse(
                {'ok': False, 'reason': 'Ya hay una peticion de respaldo pendiente.'},
                status=409,
            )
        except OSError:
            logger.exception('No se pudo escribir la peticion de respaldo')
            return JsonResponse(
                {'ok': False, 'reason': 'El servidor no acepta peticiones de respaldo.'},
                status=503,
            )

        logger.info('Respaldo solicitado por %s', request.user.get_username())
        return JsonResponse({'ok': True, 'requested_at': payload['requested_at']}, status=202)


class DatabaseRestoreRequestView(LoginRequiredMixin, UserPassesTestMixin, View):
    raise_exception = True
    http_method_names = ['post']

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body or b'{}')
        except ValueError, UnicodeDecodeError:
            return JsonResponse(
                {'ok': False, 'reason': 'La peticion no es JSON valido.'}, status=400
            )
        if not isinstance(payload, dict):
            return JsonResponse({'ok': False, 'reason': 'La peticion no es un objeto.'}, status=400)

        filename = payload.get('filename')
        if payload.get('confirm') != backup_service.RESTORE_CONFIRMATION:
            return JsonResponse(
                {
                    'ok': False,
                    'reason': f'Escriba {backup_service.RESTORE_CONFIRMATION} para confirmar.',
                },
                status=400,
            )
        if not backup_service.valid_backup_name(filename):
            return JsonResponse(
                {'ok': False, 'reason': 'El nombre del respaldo no es valido.'}, status=400
            )

        manifest = backup_service.backup_manifest(settings.DB_BACKUP_MANIFEST_FILE)
        if filename not in {item['name'] for item in manifest['backups']}:
            return JsonResponse(
                {'ok': False, 'reason': 'Ese respaldo no figura en el servidor.'}, status=400
            )

        status = backup_service.backup_status(settings.DB_BACKUP_STATUS_FILE)
        if backup_service.is_busy(status):
            return JsonResponse(
                {'ok': False, 'reason': 'Ya hay una operacion en curso.'}, status=409
            )

        try:
            backup_service.request_restore(settings.DB_RESTORE_REQUEST_FILE, request.user, filename)
        except backup_service.BackupRequestPendingError:
            return JsonResponse(
                {'ok': False, 'reason': 'Ya hay una restauracion pendiente.'}, status=409
            )
        except OSError:
            logger.exception('No se pudo escribir la peticion de restauracion')
            return JsonResponse(
                {'ok': False, 'reason': 'El servidor no acepta peticiones de restauracion.'},
                status=503,
            )

        logger.warning(
            'Restauracion de %s solicitada por %s', filename, request.user.get_username()
        )
        _audit(request, f'Solicitó restauración de {filename}')
        return JsonResponse({'ok': True, 'file': filename}, status=202)


class DatabaseDownloadRequestView(LoginRequiredMixin, UserPassesTestMixin, View):
    raise_exception = True
    http_method_names = ['post']

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body or b'{}')
        except ValueError, UnicodeDecodeError:
            return JsonResponse(
                {'ok': False, 'reason': 'La peticion no es JSON valido.'}, status=400
            )
        if not isinstance(payload, dict):
            return JsonResponse({'ok': False, 'reason': 'La peticion no es un objeto.'}, status=400)

        filename = payload.get('filename')
        if payload.get('confirm') != backup_service.DOWNLOAD_CONFIRMATION:
            return JsonResponse(
                {
                    'ok': False,
                    'reason': f'Escriba {backup_service.DOWNLOAD_CONFIRMATION} para confirmar.',
                },
                status=400,
            )
        if not backup_service.valid_backup_name(filename):
            return JsonResponse({'ok': False, 'reason': 'Nombre de respaldo invalido.'}, status=400)

        manifest = backup_service.backup_manifest(settings.DB_BACKUP_MANIFEST_FILE)
        if filename not in {item['name'] for item in manifest['backups']}:
            return JsonResponse(
                {'ok': False, 'reason': 'Ese respaldo no figura en el servidor.'}, status=400
            )

        try:
            backup_service.request_download(
                settings.DB_DOWNLOAD_REQUEST_FILE, request.user, filename
            )
        except backup_service.BackupRequestPendingError:
            return JsonResponse(
                {'ok': False, 'reason': 'Ya hay una descarga pendiente.'}, status=409
            )
        except OSError:
            logger.exception('No se pudo escribir la peticion de descarga')
            return JsonResponse(
                {'ok': False, 'reason': 'El servidor no acepta peticiones de descarga.'}, status=503
            )
        _audit(request, f'Solicitó descarga de {filename}')
        return JsonResponse({'ok': True, 'file': filename}, status=202)


class DatabaseDownloadView(LoginRequiredMixin, UserPassesTestMixin, View):
    raise_exception = True
    http_method_names = ['get']

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, token, *args, **kwargs):
        if not backup_service.valid_download_token(token):
            raise Http404

        status = backup_service.download_status(settings.DB_DOWNLOAD_STATUS_FILE)
        if not status or status.get('state') != 'ok' or status.get('token') != token:
            raise Http404

        staging = Path(settings.DB_DOWNLOAD_STAGING_DIR)
        file_path = staging / f'{token}.dump'
        try:
            real = file_path.resolve(strict=True)
            staging_real = staging.resolve(strict=True)
        except OSError:
            raise Http404 from None
        if staging_real not in real.parents:
            raise Http404
        if not real.is_file():
            raise Http404

        download_name = status.get('download_name') or status.get('file') or 'backup.dump'
        response = FileResponse(real.open('rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{smart_str(download_name)}"'
        response['X-Content-Type-Options'] = 'nosniff'

        _audit(request, f'Descargó respaldo {download_name}')
        logger.info('Descarga de %s por %s', download_name, request.user.get_username())

        # Marca consumo: elimina staging y expira estado para evitar reuso.
        try:
            real.unlink()
        except OSError:
            logger.warning('No se pudo eliminar staging de descarga %s', real)
        _mark_download_consumed(settings.DB_DOWNLOAD_STATUS_FILE)
        return response


class DatabaseUploadRestoreView(LoginRequiredMixin, UserPassesTestMixin, View):
    raise_exception = True
    http_method_names = ['post']

    def test_func(self):
        return self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        if request.POST.get('confirm') != backup_service.RESTORE_CONFIRMATION:
            return JsonResponse(
                {
                    'ok': False,
                    'reason': f'Escriba {backup_service.RESTORE_CONFIRMATION} para confirmar.',
                },
                status=400,
            )
        upload = request.FILES.get('file')
        if not upload:
            return JsonResponse({'ok': False, 'reason': 'Seleccione un archivo .dump.'}, status=400)
        name = upload.name or 'upload.dump'
        if not name.lower().endswith('.dump'):
            return JsonResponse(
                {'ok': False, 'reason': 'Solo se aceptan archivos .dump.'}, status=400
            )
        if upload.size > settings.DB_UPLOAD_MAX_SIZE:
            return JsonResponse(
                {'ok': False, 'reason': 'El archivo excede el tamaño máximo.'}, status=400
            )

        status = backup_service.backup_status(settings.DB_BACKUP_STATUS_FILE)
        if backup_service.is_busy(status):
            return JsonResponse(
                {'ok': False, 'reason': 'Ya hay una operacion en curso.'}, status=409
            )

        staging_dir = Path(settings.DB_UPLOAD_STAGING_DIR)
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_name = backup_service.make_staged_upload_name()
        staged_path = staging_dir / staged_name
        try:
            with staged_path.open('wb') as fh:
                for chunk in upload.chunks():
                    fh.write(chunk)
            os.chmod(staged_path, 0o640)
        except OSError:
            logger.exception('No se pudo guardar upload')
            staged_path.unlink(missing_ok=True)
            return JsonResponse(
                {'ok': False, 'reason': 'No se pudo guardar el archivo.'}, status=503
            )

        try:
            backup_service.request_upload_restore(
                settings.DB_RESTORE_REQUEST_FILE, request.user, staged_name, name
            )
        except backup_service.BackupRequestPendingError:
            staged_path.unlink(missing_ok=True)
            return JsonResponse(
                {'ok': False, 'reason': 'Ya hay una restauracion pendiente.'}, status=409
            )
        except Exception:
            staged_path.unlink(missing_ok=True)
            logger.exception('No se pudo crear petición de restore por upload')
            return JsonResponse(
                {'ok': False, 'reason': 'No se pudo crear la petición.'}, status=503
            )

        _audit(request, f'Subió dump para restauración: {name}')
        logger.warning('Restore por upload %s solicitado por %s', name, request.user.get_username())
        return JsonResponse({'ok': True, 'file': name}, status=202)


def _mark_download_consumed(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if isinstance(data, dict):
            data['status'] = 'expired'
            data['token'] = None
            data['message'] = 'Descarga consumida.'
            tmp = Path(str(path) + '.tmp')
            tmp.write_text(json.dumps(data), encoding='utf-8')
            os.replace(tmp, path)
    except Exception:
        logger.warning('No se pudo marcar descarga consumida', exc_info=True)


def _audit(request, message):
    try:
        log_action(request.user, request.user, CHANGE, message, request=request)
    except Exception:
        logger.warning('No se pudo auditar: %s', message, exc_info=True)
