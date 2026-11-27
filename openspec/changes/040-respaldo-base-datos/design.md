# 040-respaldo-base-datos — diseño técnico

## 1. Piezas

| Capa | Archivo | Rol |
| --- | --- | --- |
| Vista | `apps/dashboard/views/dashboard/database.py` | página, JSON de estado, peticiones |
| Servicio | `apps/dashboard/services/backup.py` | leer manifiesto/estado, validar nombres, escribir peticiones |
| URL | `apps/dashboard/urls.py` | cuatro rutas bajo `dashboard:` |
| Plantilla | `apps/dashboard/templates/pages/dashboard/database.html` | tabla, estado, modal de confirmación |
| JS | `static/dist/js/dashboard-database.js` | polling, POST, render con `textContent` |
| Menú | `templates/includes/dashboard/menu/_sistema.html` | entrada «Respaldo de la base» |
| Settings | `config/settings/base.py` | rutas de los cuatro archivos y retención |
| Ejecutor | `deploy/deploy.sh` | modos `--backup`, `--backup-manual`, `--backup-list`, `--restore`, `--restore-request` |
| Unidades | `deploy/systemd/webcmp-backup.path`, `webcmp-backup-manual.service`, `webcmp-restore.path`, `webcmp-restore.service` | disparo y ejecución root |
| Instaladores | `deploy/install.sh`, `deploy/install-backup-units.sh` | render e instalación |
| Manifiesto root | `deploy/root-bundle.manifest` | sync de las unidades nuevas |

## 2. Archivos de estado

Todos en `/var/lib/webcmp`, el directorio que ya usan deploy y apply:

| Archivo | Quién escribe | Quién lee | Modo |
| --- | --- | --- | --- |
| `backup-request` | panel (`webcmp`) | `webcmp-backup.path` | 0644 |
| `restore-request` | panel (`webcmp`) | `webcmp-restore.path` | 0644 |
| `backup-status.json` | ejecutor root | panel | 0644 |
| `backup-manifest.json` | ejecutor root | panel | 0644 |

El manifiesto solo contiene nombre, tamaño, fecha y origen. No contiene datos
de la base ni credenciales. El dump sigue en `DB_BACKUP_DIR` (`0700
root:root`) y el proceso web no puede abrirlo.

### Forma del estado

```json
{
  "kind": "backup|restore",
  "status": "running|ok|failed",
  "message": "texto fijo elegido por el ejecutor",
  "file": "webcmp-20261127T031500Z-scheduled.dump",
  "requested_by": "usuario",
  "started_at": "2026-11-27T03:15:00-05:00",
  "finished_at": "2026-11-27T03:15:04-05:00"
}
```

`message` es un texto fijo por estado, no el stderr del comando: el stderr
puede traer rutas absolutas del servidor y el panel no reenvía texto escrito
por root. El detalle queda en el journal.

### Forma del manifiesto

```json
{
  "generated_at": "2026-11-27T03:15:04-05:00",
  "dir": "/var/backups/webcmp/db",
  "keep": 10,
  "backups": [
    {"name": "...", "size": 123456, "created_at": "...", "kind": "scheduled"}
  ]
}
```

`kind` se deriva del sufijo: `-scheduled`, `-manual`, `-pre-restore`,
`-<from>-to-<sha>` (previo a migrar) o `unknown`.

## 3. Validación del nombre a restaurar

El ejecutor recibe el nombre desde un archivo escrito por `webcmp`. Se valida
en dos capas:

**Django** (antes de escribir la petición):
- el nombre debe coincidir con una entrada del manifiesto;
- debe cumplir `^[A-Za-z0-9][A-Za-z0-9._-]*\.dump$`;
- no puede contener `/`, `..` ni empezar por `-`.

**Shell** (antes de tocar la base):
- mismo patrón;
- `realpath -e` del archivo debe tener como padre exacto `realpath -e
  DB_BACKUP_DIR`;
- debe ser archivo regular, no symlink, dueño `root`.

Cualquier fallo escribe `status: failed` y **no** ejecuta `pg_restore`.

## 4. Flujo de restauración

```text
1. leer y validar restore-request
2. escribir status running
3. borrar restore-request
4. dump de seguridad -> DB_BACKUP_DIR/...-pre-restore.dump   (si falla: abortar)
5. systemctl stop webcmp webcmp-huey
6. pg_restore --clean --if-exists --single-transaction -d <base> <dump>
7. systemctl start webcmp webcmp-huey                        (siempre, en EXIT)
8. refrescar manifiesto (incluye el dump de seguridad)
9. escribir status ok|failed
```

`--single-transaction` hace el restore atómico: si algo falla a mitad, la base
queda como estaba. Aun así el dump de seguridad se toma antes, porque el
`pg_restore` puede fallar después de haber borrado objetos con `--clean`.

El paso 7 corre en un `trap EXIT` para que un fallo no deje el sitio caído: sin
el panel no hay forma de reintentar desde la web.

## 5. Permisos

- Vistas: `is_superuser`, igual que «Actualizar» y «Monitoreo».
- `raise_exception = True` en las vistas JSON: un redirect al login dentro de
  un `fetch` se ve como 200 con HTML.
- El ejecutor corre como root porque leer el dump, `pg_restore` y
  `systemctl` lo requieren. No acepta destinos fuera de `DB_BACKUP_DIR` y no
  ejecuta comandos armados con texto de la petición.

## 6. Concurrencia

- `O_EXCL` impide dos peticiones iguales mientras el archivo exista.
- El panel deshabilita los botones con `running` o petición pendiente.
- `webcmp-deploy` ya toma el lock del deploy: un respaldo manual no corre en
  paralelo con un deploy ni con el respaldo del timer.
- Una restauración en curso se detecta por `status: running` y el endpoint
  rechaza otra con 409.

## 7. Pruebas

- Django: permisos, creación de peticiones, rechazo de nombres inválidos,
  lectura tolerante de manifiesto/estado, detección de `stale`.
- Shell: validación del nombre (traversal, absoluto, symlink, no `.dump`),
  escritura de manifiesto y estado, y que el modo `--backup-manual` nombre el
  archivo como `-manual`.
- Instalador: las cuatro unidades nuevas se renderizan e instalan.
