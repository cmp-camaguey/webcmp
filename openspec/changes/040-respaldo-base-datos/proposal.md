# 040-respaldo-base-datos — propuesta

> **Estado: aprobada el 2026-11-27.** El usuario pidió «un módulo en el sistema
> que te permita desde el dashboard salvar y restaurar la base de datos» y
> eligió el alcance **solo servidor**: sin descargar ni subir `.dump`. El dump
> sigue siendo `root:root 0600` dentro de un directorio `0700`.

## 1. Motivación

El respaldo de la base ya existe y funciona, pero solo se ve por SSH:

- `webcmp-backup.timer` corre `webcmp-deploy --backup` a diario a las 03:15.
- Cada deploy con migraciones deja un dump previo en `DB_BACKUP_DIR`.
- Restaurar exige entrar al servidor, parar `webcmp` y `webcmp-huey` y correr
  `pg_restore` como root.

El contenedor de producción se entrega **sin SSH**. El panel es la única
ventana al servidor. Hoy un operador no puede pedir un respaldo antes de una
operación delicada ni volver atrás si un cambio deja la base inservible.

## 2. Solución

Un módulo «Respaldo de la base» en el menú **Sistema**, solo para
superusuarios, con tres acciones:

1. **Ver** los respaldos existentes (nombre, fecha, tamaño y origen).
2. **Respaldar ahora**: escribe una petición que recoge una unidad systemd.
3. **Restaurar** uno de los respaldos listados, con confirmación escrita.

El proceso web (`webcmp`) no gana privilegios y **nunca** lee ni escribe un
dump. El mecanismo es el mismo de los botones «Actualizar» y «Aplicar»:

```text
panel (webcmp) --escribe--> /var/lib/webcmp/{backup,restore}-request
                                      |
                          systemd .path lo ve aparecer
                                      v
                    .service root: webcmp-deploy --backup-manual
                                    webcmp-deploy --restore-request
                                      |
                                      v
                    /var/lib/webcmp/backup-status.json  (0644)
                    /var/lib/webcmp/backup-manifest.json (0644)
                                      |
                                      v
                              el panel los lee
```

El archivo de petición es **entrada no confiable**: el ejecutor solo toma de
ahí el nombre del respaldo, lo valida contra `DB_BACKUP_DIR` y, si no encaja,
falla cerrado sin tocar la base.

La restauración toma **siempre** un dump de seguridad antes de parar los
servicios. Si el `pg_restore` falla, los servicios se levantan igual y el dump
de seguridad queda listado en el panel para reintentar desde ahí.

## 3. Criterios de aceptación

- El módulo aparece en **Sistema** solo para superusuarios; un usuario sin
  permiso recibe 403 en las vistas JSON.
- El panel lista los respaldos del manifiesto y no intenta leer
  `DB_BACKUP_DIR` (que es `0700 root:root`).
- «Respaldar ahora» crea la petición con `O_EXCL`; dos peticiones simultáneas
  no se encolan.
- «Restaurar» exige un archivo del manifiesto y la palabra `RESTAURAR`; el
  nombre se valida contra traversal, rutas absolutas y symlinks.
- El ejecutor de respaldo escribe estado `running`/`ok`/`failed` y refresca el
  manifiesto; conserva la retención `DB_BACKUP_KEEP`.
- El ejecutor de restauración valida el nombre, toma el dump de seguridad,
  para los servicios, corre `pg_restore --clean --if-exists
  --single-transaction`, levanta los servicios siempre y escribe el estado.
- Las unidades nuevas se instalan con `install.sh` y
  `install-backup-units.sh`, y entran en `deploy/root-bundle.manifest`.
- `python manage.py test apps.dashboard` en verde, `make test-deploy` en
  verde, ruff y djlint limpios.
- `deploy/README-deploy.md` documenta el módulo y el flujo de restauración.

## 4. Límite de entrega

Sin descarga ni subida de dumps. Sin dependencias nuevas. Sin cambio de
esquema ni migraciones. El dump sigue sin salir del servidor por HTTP.
