# entorno-servidor Specification

Capability: `entorno-servidor` (configuración interna del servidor desde el panel)

## Purpose

Un superusuario ve desde el dashboard la configuración efectiva del servidor y
edita solo los parámetros que no comprometen el funcionamiento del sitio. Los
secretos no se renderizan nunca; los cambios se escriben en el archivo de entorno
y aplican al reiniciar el servicio, que pide el operador y ejecuta systemd, no el
proceso web.

## Requirements

### Requirement: ENTORNO-1 — Sección en el dashboard

El dashboard SHALL exponer una sección **Configuración → Entorno del servidor** en
la ruta `/config/entorno/` (`core:environment_config`), visible y accesible solo
para superusuarios.

#### Scenario: Superusuario

- GIVEN un superusuario
- WHEN abre `/config/entorno/`
- THEN recibe 200 y ve la entrada del menú

#### Scenario: Autenticado no superusuario

- GIVEN un usuario autenticado que no es superusuario
- WHEN abre `/config/entorno/`
- THEN recibe 403 y no ve la entrada del menú

### Requirement: ENTORNO-2 — Configuración efectiva

La sección SHALL mostrar los valores en ejecución leídos de
`django.conf.settings` (y de `os.environ` solo para claves que no son settings),
agrupados en: Aplicación, Dominio y orígenes, Base de datos, Caché, Correo,
LDAP, Actualizaciones del panel y Observaciones (FTP).

#### Scenario: Valores de ejecución

- GIVEN `CACHES` apunta a Redis
- WHEN se abre la página
- THEN la tarjeta de Caché informa `Redis`
- AND el perfil informa Producción o Desarrollo según `IS_PRODUCTION`

### Requirement: ENTORNO-3 — Secretos no expuestos

La página NO DEBE renderizar el valor de `SECRET_KEY`, `ENCRYPTION_KEY`, `DB_PASS`,
`EMAIL_HOST_PASSWORD`, `LDAP_BIND_PASSWORD` ni `FTP_OBS_PASS`. Solo se informa
`Configurada` o `Sin configurar`.

#### Scenario: HTML sin secretos

- GIVEN un entorno con todos los secretos configurados
- WHEN se renderiza la página
- THEN el HTML no contiene el valor de ninguno de esos secretos

### Requirement: ENTORNO-4 — Credenciales en URLs

`REDIS_URL` SHALL mostrarse sin usuario ni contraseña.

#### Scenario: URL con credenciales

- GIVEN `redis://:secreto@host:6379/1`
- WHEN se muestra la tarjeta de Caché
- THEN se lee `redis://***@host:6379/1`
- AND una URL sin credenciales se muestra igual

### Requirement: ENTORNO-5 — Parámetros editables

La sección SHALL permitir editar y escribir en el archivo de entorno únicamente:

- **Sitio**: `SITE_URL`.
- **Avisos operativos**: `EMERGENCY_BANNER_ENABLED`, `NOTIFICATIONS_ENABLED`,
  `NOTIFICATIONS_MAX_VISIBLE`, `NOTIFICATIONS_RETENTION_READ`,
  `NOTIFICATIONS_RETENTION_UNREAD`, `NOTIFICATIONS_WARNING_HORIZON_HOURS`,
  `INVOICE_PENDING_REMINDER_DAYS`.
- **Correo**: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`,
  `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`.
- **LDAP**: `LDAP_ENABLED`, `LDAP_SERVER_URI`, `LDAP_START_TLS`, `LDAP_BIND_DN`,
  `LDAP_BIND_PASSWORD`, `LDAP_USER_SEARCH_BASE`, `LDAP_GROUP_SEARCH_BASE`,
  `LDAP_STAFF_GROUP`, `LDAP_SUPERUSER_GROUP`.
- **Actualizaciones del panel**: `UPDATE_REPO_URL`, `UPDATE_BRANCH_REF`,
  `UPDATE_REPO_API`, `UPDATE_CHECK_TTL`, `UPDATE_CHECK_TIMEOUT`.
- **Observaciones (FTP)**: `FTP_OBS_HOST`, `FTP_OBS_USER`, `FTP_OBS_PASS`,
  `FTP_OBS_PORT`, `OBS_AUTOMATIC`.

#### Scenario: Guardado quirúrgico

- GIVEN un formulario con `NOTIFICATIONS_MAX_VISIBLE=25`
- WHEN se guarda
- THEN se agrega o cambia esa línea
- AND el resto del archivo queda intacto

### Requirement: ENTORNO-6 — Parámetros de solo lectura

DEBEN mostrarse en solo lectura y NO DEBEN poder modificarse desde el formulario:
`DEBUG`, `PRODUCTION`, `SECRET_KEY`, `ENCRYPTION_KEY`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `EXTERNAL_HOSTNAME`, `DB_*`,
`USE_REDIS_CACHE`, `REDIS_URL`, `EMAIL_BACKEND` y las rutas de archivo de las
actualizaciones (`UPDATE_DEPLOYED_SHA_FILE`, `UPDATE_STATUS_FILE`,
`UPDATE_REQUEST_FILE`).

Las rutas absolutas del servidor NO DEBEN mostrarse en la página: publican el
layout del sistema de archivos sin aportar nada a la operación.

`EMAIL_BACKEND` queda fuera de la lista blanca porque `production.py` levanta
`ImproperlyConfigured` si apunta a un backend que descarta correo o no verifica el
certificado: un error ahí deja el sitio sin arrancar y sin panel con el que
corregirlo.

#### Scenario: Lectura sin edición

- GIVEN la página abierta como superusuario
- WHEN se inspecciona el formulario
- THEN ninguno de esos parámetros tiene control editable
- AND ninguna ruta absoluta del servidor aparece en el HTML

### Requirement: ENTORNO-7 — Escritura segura del archivo

La escritura SHALL preservar comentarios, líneas en blanco, orden y claves ajenas
al formulario, SHALL ser atómica (temporal en el mismo directorio + `os.replace`),
SHALL conservar el modo del archivo y SHALL serializarse con `flock`.

#### Scenario: Comentarios y claves ajenas

- GIVEN un archivo con comentarios y claves desconocidas
- WHEN se guarda un cambio
- THEN ambos se conservan

#### Scenario: Valor con salto de línea

- GIVEN un valor con salto de línea
- WHEN se intenta guardar
- THEN se rechaza con `ValueError`
- AND el archivo no cambia

### Requirement: ENTORNO-8 — Archivo no escribible

Si el proceso web no puede escribir el archivo, el formulario SHALL quedar
deshabilitado con un aviso explícito y el POST NO DEBE modificar el archivo ni
registrar actividad.

#### Scenario: Permisos de solo lectura

- GIVEN un archivo de entorno sin permiso de escritura para el proceso web
- WHEN se abre la página
- THEN el formulario aparece deshabilitado con un aviso
- AND un POST no toca el archivo ni crea `ActivityLog`

### Requirement: ENTORNO-9 — Aplicación diferida

Los cambios NO DEBEN aplicarse en caliente: guardar no cambia el valor en
ejecución. La página SHALL advertir que se aplican al reiniciar el servicio y
SHALL marcar como `Pendiente de reinicio` los parámetros cuyo valor en archivo
difiere del valor en ejecución.

El reinicio solo ocurre cuando el operador lo pide con **Aplicar cambios**
(ENTORNO-16), y lo ejecuta systemd, nunca el proceso web.

#### Scenario: Drift entre archivo y ejecución

- GIVEN un valor guardado que difiere del que está en ejecución
- WHEN se abre la página
- THEN el parámetro aparece marcado `Pendiente de reinicio`
- AND un aviso explica que el sitio sigue usando el valor **En ejecución**

### Requirement: ENTORNO-10 — Auditoría

Cada guardado con cambios SHALL registrar una fila en `ActivityLog` con el
usuario, la IP, el User-Agent y las claves modificadas, sin los valores.

#### Scenario: Guardado auditado

- GIVEN un guardado con `NOTIFICATIONS_MAX_VISIBLE=25`
- WHEN termina la petición
- THEN existe una entrada de `ActivityLog` con la clave en el mensaje
- AND el número `25` no aparece en la entrada

### Requirement: ENTORNO-11 — Contraseñas editables

Los campos `EMAIL_HOST_PASSWORD`, `LDAP_BIND_PASSWORD` y `FTP_OBS_PASS` SHALL
renderizarse como campos de contraseña siempre vacíos, con un indicador
`Configurada` / `Sin configurar`. Un campo vacío NO DEBE modificar ni borrar el
valor guardado.

#### Scenario: Guardar sin escribir la contraseña

- GIVEN un secreto ya configurado
- WHEN se guarda el formulario dejando el campo vacío
- THEN el valor anterior se conserva

#### Scenario: Reemplazar la contraseña

- GIVEN un secreto ya configurado
- WHEN se escribe uno nuevo y se guarda
- THEN el valor se reemplaza
- AND el HTML nunca contiene el valor

### Requirement: ENTORNO-12 — Combinaciones que impiden arrancar

El formulario NO DEBE aceptar una combinación que `config/settings` rechace al
iniciar:

- `EMAIL_USE_TLS` y `EMAIL_USE_SSL` activos a la vez.
- `EMAIL_PORT=465` sin `EMAIL_USE_SSL`.
- `EMAIL_HOST` con `EMAIL_PORT` vacío.
- `LDAP_ENABLED` activo sin `LDAP_SERVER_URI`.
- `LDAP_ENABLED` activo sin `LDAP_USER_SEARCH_BASE`.

#### Scenario: Combinación inválida

- GIVEN cualquiera de esas combinaciones
- WHEN se envía el formulario
- THEN devuelve un error de formulario
- AND no modifica el archivo

### Requirement: ENTORNO-13 — Textos sin referencia al archivo

La página NO DEBE nombrar el archivo de entorno en sus textos visibles. La
advertencia SHALL decir que los cambios se aplican al reiniciar el servicio y que,
mientras tanto, el sitio sigue usando los valores de **En ejecución**.

#### Scenario: Aviso de la página

- GIVEN la página abierta
- WHEN se lee el aviso
- THEN nombra el reinicio del servicio y los valores **En ejecución**
- AND no nombra ningún archivo del servidor

### Requirement: ENTORNO-14 — Placeholders

Cada campo de texto o numérico SHALL mostrar un placeholder que empiece por `Ej.:`
y muestre la forma esperada del valor (por ejemplo
`Ej.: https://cmp.camaguey.cu/`, `Ej.: smtp.cmp.cu`,
`Ej.: ldap://dc.cmp.cu:389`). Los campos de contraseña SHALL usar
`Ej.: contraseña nueva`, nunca el valor guardado. Los checkboxes no llevan
placeholder.

#### Scenario: Placeholders de ejemplo

- GIVEN la página con secretos configurados
- WHEN se inspecciona el HTML
- THEN los placeholders de ejemplo están presentes
- AND ninguno coincide con un valor guardado

### Requirement: ENTORNO-15 — Nombres legibles

La página NO DEBE mostrar identificadores del código, ni como etiqueta ni como
valor: ni nombres de variables (`SECRET_KEY`, `ENCRYPTION_KEY`, `DB_PASS`,
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`,
`CONN_MAX_AGE`, `EMAIL_BACKEND`), ni rutas de módulo
(`django.core.mail.backends.smtp.EmailBackend`).

Las etiquetas SHALL estar en castellano y describir el parámetro. El motor de
correo, el de caché y el de base de datos SHALL mostrarse por su nombre (`SMTP`,
`Redis`, `PostgreSQL`), no por la ruta del módulo.

#### Scenario: Sin identificadores en el HTML

- GIVEN la página renderizada
- WHEN se busca cualquiera de esos identificadores
- THEN no aparece
- AND la tarjeta de secretos lista nombres como `Clave secreta de Django`

### Requirement: ENTORNO-16 — Aplicar cambios

La página SHALL ofrecer un botón **Aplicar cambios** junto a **Guardar**, que
guarda el formulario y pide el reinicio de los servicios en una sola acción.

- El panel NO DEBE ejecutar `systemctl`: escribe una petición y una unidad
  `systemd .path` la recoge. El proceso web no gana privilegios.
- Si ya hay una petición pendiente, NO DEBE encolar otra y SHALL avisarlo; los
  cambios igual se guardan.
- Un formulario inválido o un archivo no escribible NO DEBEN dejar petición.
- El botón SHALL quedar deshabilitado, con un aviso, cuando el proceso web no
  puede dejar la petición.
- El botón SOLO SHALL habilitarse con el modo mantenimiento activo
  (`SiteConfiguration.maintenance_mode`), y el POST de aplicar SHALL rechazarse
  fuera de esa ventana sin escribir el archivo ni dejar petición.
- La página SHALL mostrar el estado del último reinicio: en curso, completado,
  fallido o sin confirmar. Un estado ilegible NO DEBE presentarse como resultado.

#### Scenario: Aplicar con la ventana abierta

- GIVEN mantenimiento activo y un cambio en el formulario
- WHEN se pulsa **Aplicar cambios**
- THEN el cambio se guarda
- AND se crea la petición de reinicio con el usuario

#### Scenario: Ya hay un reinicio pedido

- GIVEN una petición pendiente en disco
- WHEN se vuelve a aplicar
- THEN el archivo no se sobrescribe
- AND la página avisa que ya hay un reinicio en curso

#### Scenario: Fuera de la ventana

- GIVEN el modo mantenimiento apagado
- WHEN se envía el POST de aplicar
- THEN se rechaza sin escribir el archivo ni dejar petición

### Requirement: ENTORNO-17 — Aviso de petición sin recoger

Pasados `PENDING_GRACE_SECONDS` (30 s) desde la escritura de `apply-request`, la
página SHALL mostrar un aviso que diga que la petición quedó sin recoger, con la
hora, el autor si se puede leer y qué revisar en el servidor.

- NO DEBE mostrar el aviso dentro del margen: la página se repinta justo después
  de crear el archivo.
- SHALL mostrarlo aunque el archivo esté vacío o con JSON inválido.
- NO DEBE reemplazar el estado del último reinicio: son hechos distintos.

#### Scenario: Petición vieja

- GIVEN `apply-request` escrito hace más de 30 s
- WHEN se abre la página
- THEN aparece el aviso de petición sin recoger
- AND el estado del último reinicio se sigue mostrando por separado

#### Scenario: Dentro del margen

- GIVEN `apply-request` recién escrito
- WHEN la página se repinta
- THEN el aviso no aparece

### Requirement: ENTORNO-18 — Pruebas

La suite SHALL cubrir permiso y render, enmascarado de secretos, escritura
quirúrgica, combinaciones inválidas, drift y aviso, auditoría, el aviso de
petición sin recoger y las dos vistas en `apps/core/tests/test_env_config.py`.
