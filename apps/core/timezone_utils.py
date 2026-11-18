"""Estado de formato de hora por request.

Django activa la zona horaria en un thread-local; el formato de 12/24 horas
necesita el mismo alcance. `SiteTimezoneMiddleware` guarda aquí el patrón
elegido en `SiteConfiguration` y los filtros de plantilla lo leen.

Si no hay request (tareas de Huey, pruebas directas de plantillas), el valor por
defecto es 24 horas, que es el `default` del modelo.
"""

import threading

_thread_locals = threading.local()

DEFAULT_TIME_FORMAT = 'H:i'


def set_request_time_format(pattern):
    _thread_locals.time_format = pattern


def get_request_time_format():
    value = getattr(_thread_locals, 'time_format', None)
    return value or DEFAULT_TIME_FORMAT


def get_request_clock_pattern(with_seconds=False):
    """Patrón de hora (con o sin segundos) según el formato configurado.

    Los servicios que arman horas para el panel usan esto en vez de escribir
    `%H:%M` a mano: si el sitio está en 12 horas, la hora sale con AM/PM.
    """
    pattern = get_request_time_format()
    if with_seconds:
        return 'h:i:s A' if 'A' in pattern else 'H:i:s'
    return pattern


def reset_request_time_format():
    _thread_locals.time_format = None
