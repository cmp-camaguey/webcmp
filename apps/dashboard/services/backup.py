"""Respaldo y restauracion de la base desde el panel (change 040).

El proceso web corre como ``webcmp`` y no tiene privilegios: no puede leer el
dump (``root:root 0600`` dentro de un directorio ``0700``), no puede ejecutar
``pg_dump`` ni ``pg_restore`` y no puede parar los servicios. El mecanismo es el
mismo de los botones "Actualizar" y "Aplicar": el panel deja una peticion en un
directorio que le pertenece, una unidad ``systemd .path`` la ve aparecer y un
ejecutor root hace el trabajo.

Este modulo es la mitad del panel de ese contrato: escribe las peticiones y lee
los dos archivos que deja el ejecutor. Nada de lo que hay aca toca la base ni
abre un dump.

Los dos archivos de salida los escribe otro usuario, asi que su contenido no se
usa tal cual: se valida la forma y, si no encaja, se ignora. Un JSON a medias no
puede tumbar el panel.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from django.utils import timezone

logger = logging.getLogger(__name__)

# Una restauracion de una base grande puede tardar minutos, pero no una hora.
# Pasado este plazo, un `running` no describe una operacion en curso sino una
# que se quedo sin final: systemd mato la unidad por timeout o el ejecutor no
# llego a escribir el desenlace.
RUN_STALE_SECONDS = 3600

# Margen antes de declarar huerfana una peticion. El ejecutor la consume en
# milisegundos; sin margen, el primer render diria "nadie la recogio" de una
# peticion que si se estaba procesando.
PENDING_GRACE_SECONDS = 30

# Lo que el operador tiene que escribir para confirmar una restauracion. No es
# un "OK" de un clic: restaurar borra y recrea los objetos de la base.
RESTORE_CONFIRMATION = 'RESTAURAR'

# El nombre lo escribe el panel, pero el ejecutor lo trata como entrada no
# confiable. Se valida en las dos capas: aca y en `deploy.sh`.
BACKUP_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*\.dump$')

# Origenes que entiende el manifiesto. Un valor desconocido se muestra como
# `unknown` en vez de descartar el respaldo: el archivo existe y se puede
# restaurar aunque su nombre no siga la convencion.
MANIFEST_KINDS = {'scheduled', 'manual', 'pre-restore', 'pre-migrate', 'unknown'}


class BackupRequestPendingError(Exception):
    """Ya hay una peticion en disco: no se encola otra."""


def valid_backup_name(name) -> bool:
    """¿Es un nombre de dump que el ejecutor puede aceptar?

    Solo el nombre, nunca una ruta: sin separadores, sin ``..`` y con el
    sufijo ``.dump``. El ejecutor repite esta validacion y ademas resuelve la
    ruta contra ``DB_BACKUP_DIR``; esta capa existe para no escribir una
    peticion que se va a rechazar.
    """
    if not isinstance(name, str) or not BACKUP_NAME_RE.match(name):
        return False
    return '..' not in name


def can_request(path) -> bool:
    """¿Puede el proceso web dejar la peticion en `path`?

    Lo que manda es el permiso del DIRECTORIO: el archivo se crea con
    ``O_EXCL``, asi que nunca se escribe sobre uno existente.
    """
    return os.access(Path(path).parent, os.W_OK | os.X_OK)


def request_backup(path, user) -> dict:
    """Deja la peticion de respaldo.

    Lanza `BackupRequestPendingError` si ya hay una, y `OSError` si el
    directorio no acepta el archivo.
    """
    return _write_request(
        path,
        {
            'requested_by': user.get_username(),
            'requested_at': datetime.now(UTC).isoformat(),
        },
    )


def request_restore(path, user, filename) -> dict:
    """Deja la peticion de restauracion con el dump elegido.

    El nombre se valida aca otra vez: la vista ya lo contrasto con el
    manifiesto, pero esta funcion es la unica puerta de escritura y no confia
    en quien la llame.
    """
    if not valid_backup_name(filename):
        raise ValueError(f'Nombre de respaldo invalido: {filename!r}')
    return _write_request(
        path,
        {
            'file': filename,
            'requested_by': user.get_username(),
            'requested_at': datetime.now(UTC).isoformat(),
        },
    )


def pending_request(
    path,
    now=None,
    *,
    label='respaldo',
    unit='webcmp-backup.path',
) -> dict | None:
    """Peticion que nadie recogio, o `None` si no hay ninguna.

    El ejecutor borra el archivo ANTES de hacer nada, asi que una peticion que
    sigue en disco y ya paso el margen no esta "en curso": no la proceso nadie.
    Sin esta comprobacion el panel no distingue "nadie la recogio" de "nunca se
    pidio", y las dos se ven igual: ningun aviso. Es el estado en el que queda
    un servidor al que le falta la unidad ``systemd`` que vigila el archivo.
    """
    try:
        modified = os.stat(path).st_mtime
    except OSError:
        return None

    reference = (now or datetime.now(UTC)).timestamp()
    if reference - modified < PENDING_GRACE_SECONDS:
        # Recien escrita: el ejecutor todavia puede recogerla.
        return None

    raw = _read_json(path) or {}
    requested_by = str(raw.get('requested_by') or '').strip()
    who = f' (solicitada por {requested_by})' if requested_by else ''
    clock = _clock(datetime.fromtimestamp(modified, tz=UTC))
    return {
        'tone': 'warning',
        'color': 'orange',
        'icon': 'plug-off',
        'text': (
            f'La peticion de {label} de las {clock} quedo sin recoger{who}. '
            f'Ningun proceso la proceso: revise systemctl status {unit} en el servidor.'
        ),
    }


def backup_status(path, now=None) -> dict | None:
    """Estado legible de la ultima operacion, o `None` si no hay nada.

    Un archivo ilegible o con una forma que no se reconoce devuelve `None`: el
    panel no puede inventar un resultado a partir de datos que no entiende.
    """
    raw = _read_json(path)
    if raw is None:
        return None

    kind = str(raw.get('kind') or '').strip().lower()
    if kind not in ('backup', 'restore'):
        return None

    state = str(raw.get('status') or '').strip().lower()
    if state not in ('running', 'ok', 'failed'):
        return None

    requested_by = str(raw.get('requested_by') or '').strip()
    started = _parse_instant(raw.get('started_at'))
    finished = _parse_instant(raw.get('finished_at'))
    file = raw.get('file')
    file = file if valid_backup_name(file) else None
    safety = raw.get('safety_file')
    safety = safety if valid_backup_name(safety) else None

    if state == 'running' and _is_stale(started, now):
        state = 'stale'

    return {
        'state': state,
        'kind': kind,
        'tone': _TONES[state],
        'color': _COLORS[_TONES[state]],
        'icon': _ICONS[state],
        'text': _status_text(
            state,
            kind=kind,
            file=file,
            safety=safety,
            requested_by=requested_by,
            started=started,
            finished=finished,
        ),
        'file': file,
        'safety_file': safety,
        'requested_by': requested_by,
        'started_at': started.isoformat() if started else None,
        'finished_at': finished.isoformat() if finished else None,
    }


def backup_manifest(path) -> dict:
    """Manifiesto saneado. Siempre devuelve la misma forma.

    Una entrada invalida se descarta sin arrastrar a las demas: el manifiesto
    lo escribe root, pero un archivo a medias no puede vaciar la lista entera ni
    meter un nombre con ``/`` en un boton de restaurar.
    """
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return _empty_manifest()

    backups = []
    entries = raw.get('backups')
    if isinstance(entries, list):
        for entry in entries:
            clean = _clean_entry(entry)
            if clean is not None:
                backups.append(clean)

    keep = raw.get('keep')
    return {
        'generated_at': raw.get('generated_at')
        if isinstance(raw.get('generated_at'), str)
        else None,
        'dir': raw.get('dir') if isinstance(raw.get('dir'), str) else None,
        'keep': keep if isinstance(keep, int) and not isinstance(keep, bool) else None,
        'backups': backups,
    }


def is_busy(status) -> bool:
    """¿Hay una operacion en curso que impida encolar otra?

    `stale` no cuenta: si el estado quedo colgado, bloquear el boton para
    siempre deja al operador sin salida. Se avisa en el panel y se permite
    reintentar.
    """
    return bool(status) and status.get('state') == 'running'


def _write_request(path, payload) -> dict:
    try:
        # O_EXCL y no un write normal: dos pestanas con el boton pulsado a la vez
        # no deben encolar dos operaciones.
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as error:
        raise BackupRequestPendingError from error
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)
    return payload


def _empty_manifest() -> dict:
    return {'generated_at': None, 'dir': None, 'keep': None, 'backups': []}


def _clean_entry(entry) -> dict | None:
    if not isinstance(entry, dict):
        return None
    name = entry.get('name')
    if not valid_backup_name(name):
        return None
    size = entry.get('size')
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        return None
    created = entry.get('created_at')
    # Un manifiesto escrito a mano puede no traer la fecha; el respaldo sigue
    # siendo restaurable y el panel la muestra como "—".
    created = created if isinstance(created, str) else None
    kind = entry.get('kind')
    if kind not in MANIFEST_KINDS:
        kind = 'unknown'
    return {'name': name, 'size': size, 'created_at': created, 'kind': kind}


# La plantilla no decide colores: el estado ya sabe como se ve. Asi un estado
# nuevo no se queda sin estilo porque alguien olvido tocar el HTML.
_TONES = {
    'running': 'info',
    'ok': 'success',
    'failed': 'danger',
    'stale': 'warning',
}

# Mismos nombres de color que los badges del panel (bg-*-lt).
_COLORS = {
    'info': 'blue',
    'success': 'green',
    'danger': 'red',
    'warning': 'orange',
}

_ICONS = {
    'running': 'loader',
    'ok': 'circle-check',
    'failed': 'alert-triangle',
    'stale': 'clock-exclamation',
}


def _read_json(path) -> dict | None:
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
    except OSError, ValueError:
        # `ValueError` cubre el JSON a medias: el ejecutor escribe con
        # `os.replace`, pero un archivo escrito a mano puede estar roto y la
        # pagina no puede caerse por eso.
        return None
    return data if isinstance(data, dict) else None


def _parse_instant(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    # El ejecutor escribe con `date -Is`, que lleva el desfase de la zona del
    # servidor. Un valor sin zona se interpreta como UTC en vez de descartarse.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _is_stale(started: datetime | None, now: datetime | None) -> bool:
    if started is None:
        # Un `running` sin instante de arranque no se puede acotar, y dejarlo
        # "en curso" para siempre es peor que decir que quedo sin confirmar.
        return True
    reference = now or datetime.now(UTC)
    return (reference - started).total_seconds() > RUN_STALE_SECONDS


def _status_text(state, *, kind, file, safety, requested_by, started, finished) -> str:
    who = f' (solicitado por {requested_by})' if requested_by else ''
    when = f' el {_instant(finished)}' if finished else ''
    if kind == 'restore':
        if state == 'running':
            since = f' desde las {_clock(started)}' if started else ''
            return f'Restauracion en curso{since}{who}: el sitio se reinicia y vuelve solo.'
        if state == 'ok':
            return f'Ultima restauracion completada{when}{who}.'
        if state == 'failed':
            tail = (
                f' Si el sitio no responde, restaure el respaldo de seguridad {safety}.'
                if safety
                else ''
            )
            return f'La ultima restauracion fallo.{tail}'
        return (
            'La ultima restauracion quedo sin confirmar. '
            'Revise el journal de webcmp-restore en el servidor.'
        )

    if state == 'running':
        since = f' desde las {_clock(started)}' if started else ''
        return f'Respaldo en curso{since}{who}.'
    if state == 'ok':
        target = f' ({file})' if file else ''
        return f'Ultimo respaldo completado{when}{who}{target}.'
    if state == 'failed':
        return 'El ultimo respaldo fallo. Revise el journal de webcmp-backup en el servidor.'
    return (
        'El ultimo respaldo quedo sin confirmar. Revise el journal de webcmp-backup en el servidor.'
    )


def _instant(value: datetime) -> str:
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')


def _clock(value: datetime) -> str:
    return timezone.localtime(value).strftime('%H:%M')
