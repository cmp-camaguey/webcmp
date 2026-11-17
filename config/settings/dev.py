"""Perfil `dev`: desarrollo local con `DEBUG=True`."""

import logging
import os

from .base import *  # noqa: F403
from .base import (  # noqa: F401  (alias sin guion bajo: `import *` no lo exporta)
    _CONTENT_SECURITY_POLICY_DIRECTIVES,
    apply_external_hostname,
    resolve_obs_local_only,
)

DEBUG = True

if 'EMAIL_BACKEND' not in os.environ:
    EMAIL_BACKEND = console_email_backend

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

DEBUG_TOOLBAR_ENABLED = True
INTERNAL_IPS = ['127.0.0.1', '::1']
DEBUG_TOOLBAR_CONFIG = {'IS_RUNNING_TESTS': False}

INSTALLED_APPS = [*INSTALLED_APPS, 'debug_toolbar']
MIDDLEWARE = [mw for mw in MIDDLEWARE if mw != whitenoise_middleware] + [
    'debug_toolbar.middleware.DebugToolbarMiddleware'
]

# Dev usa el mismo motor que producción. No hay archivo SQLite de respaldo: si
# falta `DB_ENGINE`, el arranque falla en vez de medir un motor que no existe en
# el servidor.
DATABASES = get_database_config()

if external_hostname := os.getenv('EXTERNAL_HOSTNAME', ''):
    apply_external_hostname(external_hostname, ['http://'])

OBS_LOCAL_ONLY_DEFAULT = True
OBS_LOCAL_ONLY = resolve_obs_local_only(OBS_LOCAL_ONLY_DEFAULT)

if os.getenv('LDAP_SERVER_URI'):
    logging.getLogger('ldap3_auth').setLevel(logging.DEBUG)

# El modal «Ver log del despliegue» solo lee UPDATE_LOG_FILE: en dev el archivo
# de producción no existe y el botón no tendría nada que mostrar. Apuntarlo a
# un ejemplo versionado deja ver el render real (ANSI limpio, colores y
# numeración). Un UPDATE_LOG_FILE
# explícito del entorno gana: base.py ya lo respetó al importarse.
if 'UPDATE_LOG_FILE' not in os.environ:
    UPDATE_LOG_FILE = str(BASE_DIR / 'deploy' / 'examples' / 'deploy-demo.log.example')
