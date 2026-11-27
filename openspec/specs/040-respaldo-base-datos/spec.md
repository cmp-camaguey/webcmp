# 040-respaldo-base-datos — requisitos

## S1 — Acceso y menú

El módulo DEBE vivir bajo el namespace `dashboard` y ser accesible solo a
superusuarios.

- La entrada «Respaldo de la base» DEBE aparecer en el menú **Sistema** solo
  cuando `request.user.is_superuser`.
- Las vistas JSON DEBEN responder 403 a un usuario autenticado sin
  superusuario y redirigir al login a un anónimo.
- Aceptación: `apps/dashboard/tests/test_database_backup.py`.

## S2 — Listado desde el manifiesto

El panel DEBE listar los respaldos leyendo
`/var/lib/webcmp/backup-manifest.json`, nunca `DB_BACKUP_DIR`.

- Cada entrada DEBE exponer `name`, `size`, `created_at` y `kind`.
- Un manifiesto ausente, ilegible o con forma inválida DEBE producir una lista
  vacía, sin excepción.
- Aceptación: pruebas del servicio y de `DatabaseBackupDataView`.

## S3 — Respaldar ahora

`POST /dashboard/database/backup/` DEBE crear
`/var/lib/webcmp/backup-request` con `O_EXCL`.

- Si el archivo ya existe, DEBE responder 409.
- Si el directorio no acepta escritura, DEBE responder 503.
- Django NO DEBE ejecutar `pg_dump` ni leer `DB_BACKUP_DIR`.
- Aceptación: pruebas de `request_backup` y de la vista.

## S4 — Restaurar

`POST /dashboard/database/restore/` DEBE aceptar JSON con `filename` y
`confirm`.

- `filename` DEBE existir en el manifiesto y cumplir
  `^[A-Za-z0-9][A-Za-z0-9._-]*\.dump$`.
- `confirm` DEBE ser exactamente `RESTAURAR`.
- Si hay una operación `running` o una petición pendiente, DEBE responder 409.
- Un nombre desconocido o inválido DEBE responder 400 y no escribir nada.
- Aceptación: pruebas de `request_restore` y de la vista.

## S5 — Ejecutor de respaldo

`webcmp-deploy --backup` (timer) y `--backup-manual` (panel) DEBEN compartir la
implementación.

- Al empezar DEBEN escribir `status: running` y borrar `backup-request`.
- Al terminar DEBEN escribir `status: ok` o `failed` y refrescar el
  manifiesto.
- El nombre DEBE terminar en `-scheduled.dump` o `-manual.dump` según el modo.
- DEBEN conservar la retención `DB_BACKUP_KEEP` y el modo `0600` del dump.
- Aceptación: `deploy/tests/test_deploy_sh_backup_mode.sh` y
  `test_deploy_sh_backup_panel.sh`.

## S6 — Ejecutor de restauración

`webcmp-deploy --restore-request` DEBE leer y validar la petición antes de
tocar la base.

- El nombre DEBE cumplir el patrón, resolver dentro de `DB_BACKUP_DIR`, ser
  archivo regular, no symlink y dueño `root`.
- Un nombre inválido DEBE escribir `status: failed` y salir sin ejecutar
  `pg_restore`.
- Antes de parar servicios DEBE tomar un dump `-pre-restore.dump`; si falla,
  DEBE abortar sin tocar la base.
- DEBE parar `webcmp` y `webcmp-huey`, correr
  `pg_restore --clean --if-exists --single-transaction`, y levantarlos
  **siempre**, incluso si el restore falla.
- DEBE escribir `status: ok|failed` y refrescar el manifiesto.
- Aceptación: pruebas del bloque de validación y del flujo con stubs.

## S7 — Unidades e instalación

- `webcmp-backup.path` DEBE disparar `webcmp-backup-manual.service`.
- `webcmp-restore.path` DEBE disparar `webcmp-restore.service`.
- `install.sh` y `install-backup-units.sh` DEBEN instalar y habilitar las
  unidades nuevas de forma idempotente.
- Las cuatro unidades DEBEN figurar en `deploy/root-bundle.manifest`.
- Aceptación: `deploy/tests/test_install_backup_units.sh`.

## S8 — Documentación

`deploy/README-deploy.md` DEBE documentar el módulo, el flujo de restauración,
el dump de seguridad y que el panel nunca lee el dump.

- Aceptación: revisión del documento.
