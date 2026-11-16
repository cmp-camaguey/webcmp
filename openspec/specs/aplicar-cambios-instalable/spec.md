# aplicar-cambios-instalable Specification

Capability: `aplicar-cambios-instalable` (instalación y operación de las piezas de «Aplicar cambios»)

## Purpose

El botón **Aplicar cambios** del panel escribe una petición que recoge una unidad
`systemd .path`; estas son las piezas que la dejan instalada y operativa sin volver
a correr `install.sh`. El comportamiento del botón y de la página vive en
`entorno-servidor`; el aviso del panel cuando la petición queda sin recoger es
`ENTORNO-17`.

## Requirements

### Requirement: APLICAR-1 — Instalador de las piezas

`deploy/install-apply-units.sh` SHALL instalar, como root y en una sola corrida,
las tres piezas del botón: `/usr/local/sbin/webcmp-apply-env` (`root:root 0755`),
`webcmp-apply.service` y `webcmp-apply.path` (`root:root 0644`), recargar
`systemd` y habilitar el `.path`.

- SHALL ser idempotente: una segunda corrida no reescribe ningún archivo y lo
  informa.
- SHALL renderizar el unit desde `APP_DIR`, `APPLY_SCRIPT`, `SERVICE_GROUP`,
  `GUNICORN_UNIT`, `HUEY_UNIT` y `APPLY_UNIT`, sustituyendo de forma literal.
- SHALL aceptar `--help` sin root, y `DRY_RUN=1` para mostrar los comandos sin
  ejecutarlos.
- NO DEBE tocar el `.env`, la base, el venv, el código ni `install.sh`.

#### Scenario: Instalación y segunda corrida

- GIVEN un servidor sin las piezas
- WHEN se corre el instalador como root
- THEN las tres quedan con su dueño y modo, `systemd` recarga y el `.path` queda habilitado
- AND una segunda corrida no reescribe archivos y lo informa

#### Scenario: Ayuda sin root

- GIVEN un usuario sin root
- WHEN se corre con `--help`
- THEN la ayuda nombra las piezas
- AND advierte que no toca el `.env`

### Requirement: APLICAR-2 — Negarse a habilitar el `.path` con una petición pendiente

Si existe `$APPLY_STATE_DIR/apply-request`, el instalador SHALL abortar antes de
habilitar nada, nombrar la ruta del archivo y decir cómo destrabarlo.

Motivo: `PathExists=` dispara ese reinicio en el instante en que la unidad queda
activa, fuera de la ventana de mantenimiento.

#### Scenario: Petición en disco

- GIVEN `apply-request` presente
- WHEN se corre el instalador
- THEN sale con código 1 y nombra la ruta
- AND no invoca `systemctl enable`

#### Scenario: Sin petición

- GIVEN el archivo ausente
- WHEN se corre el instalador
- THEN continúa con la instalación

### Requirement: APLICAR-3 — `deploy.sh` se niega a desplegar sin las unidades que el commit pide

Cada `deploy/systemd/*.service` y `*.path` del commit SHALL existir en
`/etc/systemd/system` (con el nombre renderizado, si `install.sh` puede cambiarlo)
antes de instalar dependencias o migrar. Si falta alguna, el deploy SHALL abortar
listándolas y nombrando el instalador.

- La comprobación SHALL correr después de `git checkout` y antes de `pip install`.
- `--check` SHALL reportar lo mismo sin desplegar.
- El deploy NO DEBE instalar las unidades.

#### Scenario: Unidad faltante

- GIVEN el commit trae `webcmp-apply.path` y no está en `/etc/systemd/system`
- WHEN se corre el deploy
- THEN aborta listando la unidad y nombrando el instalador
- AND no instala dependencias ni migra

#### Scenario: `--check`

- GIVEN la misma falta
- WHEN se corre con `--check`
- THEN reporta lo mismo sin desplegar

### Requirement: APLICAR-4 — El deploy deja el botón operativo

Cuando el `.path` ya está instalado, el deploy SHALL habilitarlo y arrancarlo
después de reiniciar los servicios y antes del health check, y SHALL abortar si no
queda activo.

- Si existe una petición en disco, SHALL descartarla informándolo: el reinicio del
  propio deploy la cumple.
- Si la unidad no está instalada, NO DEBE hacer nada (el guard de APLICAR-3 ya
  abortó).
- `--check` SHALL reportar el `.path` instalado pero no habilitado como falla.

Motivo: el operador aplica el arreglo con el botón **Actualizar**; un deploy que
termina «ok» con el botón muerto es el defecto original.

#### Scenario: Botón operativo al terminar

- GIVEN el `.path` instalado y detenido
- WHEN termina el deploy
- THEN el `.path` queda habilitado y activo antes del health check
- AND una petición previa en disco se descarta informándolo

### Requirement: APLICAR-5 — Documentación

`deploy/README-deploy.md` SHALL explicar cómo instalar o reparar estas piezas sin
volver a correr `install.sh`, y la tabla de estados SHALL incluir el caso «sin
recoger». `deploy/deploy.env.example` SHALL documentar `AUTODEPLOY_UNIT` y
`APPLY_UNIT`.

#### Scenario: Ningún documento manda `install.sh`

- GIVEN la documentación de deploy
- WHEN se busca cómo reparar el botón
- THEN la respuesta no es correr `install.sh`

### Requirement: APLICAR-6 — Pruebas

La suite SHALL cubrir el render literal, la negativa con petición pendiente, la
instalación real (solo como root), `missing_units` con árboles temporales,
`ensure_apply_path` y el aviso del panel.

#### Scenario: Suite en verde

- GIVEN los cambios aplicados
- WHEN se corre `make test-deploy` y `python manage.py test apps.core`
- THEN ambos terminan en verde
