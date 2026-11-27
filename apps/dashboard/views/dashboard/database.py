"""Respaldo y restauracion de la base desde el panel (change 040).

Cuatro vistas, todas para superusuarios, igual que "Actualizar" y "Monitoreo":

- la pagina, que pinta el estado y la lista;
- un JSON con el mismo estado, para el polling del JS;
- la peticion de respaldo;
- la peticion de restauracion.

Ninguna ejecuta `pg_dump`, `pg_restore` ni `systemctl`. Escriben una peticion
que recoge una unidad systemd y leen dos archivos que deja el ejecutor root. Un
proceso web comprometido consigue, como mucho, pedir un respaldo de la base o
una restauracion de un dump que ya existe en el directorio del servidor.
"""

import json
import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.dashboard.services import backup as backup_service

logger = logging.getLogger(__name__)


class DatabaseBackupView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Pagina del modulo."""

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
                'confirmation': backup_service.RESTORE_CONFIRMATION,
            }
        )
        return context


class DatabaseBackupDataView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Estado y manifiesto, como JSON.

    ``raise_exception`` a proposito: estas vistas son JSON y un redirect al
    login en un ``fetch`` se ve como un 200 con HTML, no como un permiso
    denegado.
    """

    raise_exception = True
    http_method_names = ['get']

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, *args, **kwargs):
        return JsonResponse(
            {
                'status': backup_service.backup_status(settings.DB_BACKUP_STATUS_FILE),
                'manifest': backup_service.backup_manifest(settings.DB_BACKUP_MANIFEST_FILE),
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
                'can_request': backup_service.can_request(settings.DB_BACKUP_REQUEST_FILE),
            }
        )


class DatabaseBackupRequestView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Deja la peticion que recoge `webcmp-backup.path`."""

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
    """Deja la peticion que recoge `webcmp-restore.path`.

    El nombre se contrasta con el manifiesto: solo se puede restaurar un dump
    que el ejecutor root ya listo. La confirmacion escrita evita el clic
    accidental sobre una operacion que borra y recrea los objetos de la base.
    """

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
                    'reason': (f'Escriba {backup_service.RESTORE_CONFIRMATION} para confirmar.'),
                },
                status=400,
            )
        if not backup_service.valid_backup_name(filename):
            return JsonResponse(
                {'ok': False, 'reason': 'El nombre del respaldo no es valido.'},
                status=400,
            )

        manifest = backup_service.backup_manifest(settings.DB_BACKUP_MANIFEST_FILE)
        if filename not in {item['name'] for item in manifest['backups']}:
            return JsonResponse(
                {'ok': False, 'reason': 'Ese respaldo no figura en el servidor.'},
                status=400,
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
                {
                    'ok': False,
                    'reason': 'El servidor no acepta peticiones de restauracion.',
                },
                status=503,
            )

        logger.warning(
            'Restauracion de %s solicitada por %s',
            filename,
            request.user.get_username(),
        )
        return JsonResponse({'ok': True, 'file': filename}, status=202)
