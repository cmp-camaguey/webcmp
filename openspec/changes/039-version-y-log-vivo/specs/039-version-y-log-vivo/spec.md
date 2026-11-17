# 039-version-y-log-vivo — requisitos

## S1 — La regla del tag exacto

La versión de un commit DEBE ser un tag que apunte **exacto** a ese commit,
comparando contra el SHA peeled (`refs/tags/<tag>^{}`) cuando exista y contra
el propio SHA para tags ligeros.

- `_ls_remote()` DEBE pedir `refs/heads/main` y `refs/tags/*` en una sola
  llamada, y parsear solo líneas con forma de SHA.
- Entre varios tags apuntando al mismo commit, la preferencia DEBE ser
  determinista: `v*` antes que cualquier otro nombre, y dentro de `v*` el
  estable (`vX.Y.Z`) antes que el prerelease (`vX.Y.Z-rc.N`).
- Sin tag exacto la versión DEBE ser `None`: nunca un tag aproximado.
- Aceptación: pruebas de `_version_for()` y del parseo de `tags`.

## S2 — Las dos versiones en el payload

`build_state()` DEBE incluir `deployed_version` (tag exacto del commit
desplegado) y `version` (tag exacto del commit remoto), como string o
`None`.

- Aceptación: `UpdateStatusViewTest` y `BuildStateTest` cubren ambos campos
  con tag presente y ausente.

## S3 — Chip, botón y detalle

El menú de actualizaciones DEBE mostrar un chip con la versión
(`update-navbar-version`), pintado con `textContent`.

- Con versión, el botón DEBE decir «Actualizar a vX.Y.Z» y el detalle
  «Instala vX.Y.Z (sha)…».
- Sin tag exacto, el chip DEBE mostrar el SHA corto y el botón y el detalle
  DEBEN conservar el texto actual («Actualizar ahora», rango de SHA): nada
  se inventa.
- Aceptación: `python manage.py test apps.dashboard` y revisión visual.

## S4 — Log en vivo en el modal

Con el modal de log abierto y el estado en `running`, el JS DEBE relear el
log en cada ciclo de polling (2 s); al salir de `running` DEBE hacer una
última lectura.

- El autoscroll DEBE aplicarse solo si el lector está al final del `pre`
  antes de la relectura; una posición de lectura intermedia se conserva.
- Sin modal abierto o fuera de `running`, no DEBE haber lecturas extra.
- El contenido DEBE escribirse con `textContent`, nunca `innerHTML`.
- Aceptación: `python manage.py test apps.dashboard` + revisión del JS.

## S5 — Sin transporte nuevo

El cambio DEBE resolverse con el polling y el endpoint `update_log` que ya
existen: sin SSE, sin WebSocket, sin dependencias nuevas.

## S6 — Documentación

`deploy/README-deploy.md` DEBE documentar en «El botón 'Actualizar' del
panel» el chip de versión, la regla del tag exacto y el log en vivo.

## S7 — Entrega sin comandos en el servidor

Ningún archivo de este cambio vive fuera del repo: después del deploy de
v0.7.4 ningún camino DEBE exigir un comando en el server.
