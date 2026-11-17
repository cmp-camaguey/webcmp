# 037-log-del-despliegue — requisitos

## S1 — El ejecutor escribe el log a un archivo

`deploy/autodeploy.sh` DEBE escribir cada intento a `$DEPLOY_LOG`
(`/var/lib/webcmp/deploy.log`) además del journal, con la misma corriente
(`tee -a`), y el archivo DEBE quedar en 0644 legible para el proceso web.

- El código de salida del bloque DEBE ser el del deploy (`PIPESTATUS[0]`), no el
  de `tee`.
- Un log inescribible NO DEBE tumbar un deploy que salió bien ni impedir que el
  estado del panel se escriba.
- Aceptación: `deploy/tests/test_autodeploy_log.sh` cubre los cinco caminos.

## S2 — El propio ejecutor rota el archivo

Antes de cada corrida, si `$DEPLOY_LOG` pasa de `DEPLOY_LOG_MAX_BYTES`
(524288), `prepare_log()` DEBE conservar la última mitad por bytes y informar
nada más si el archivo no existe.

- Nadie más rota este archivo: no hay `logrotate` en el contenedor.
- Aceptación: el test de recorte verifica que no crece sin techo y que conserva
  lo último.

## S3 — El panel devuelve la cola del log

`GET /dashboard/update/log/` (superusuario, JSON) DEBE devolver
`{"available": true, "log": "...", "truncated": bool}` con los últimos
`UPDATE_LOG_MAX_BYTES` (32768) del archivo, o `available: false` si no existe o
no se puede leer.

- Si el corte cae a mitad de una línea, DEBE descartar el renglón parcial.
- NO DEBE filtrar el contenido: lo ve el superusuario que ya dispara los deploys.
- Un error de lectura DEBE responder `available: false`, nunca un 500.
- Aceptación: `UpdateLogViewTest` en `apps/dashboard/tests/test_update.py`.

## S4 — Mismo público que el estado

La vista DEBE exigir superusuario con `raise_exception = True` (403, no
redirect), igual que `UpdateStatusView` y `UpdateRequestView`.

- Aceptación: tests de anónimo y de usuario staff.

## S5 — El desplegable abre el log en un modal

El navbar del dashboard DEBE mostrar siempre el botón **"Ver log del
despliegue"** (no solo tras un fallo) con un modal que carga el log al abrirse
(`show.bs.modal`), no en el polling, y lo pinta con `textContent`.

- Si no hay log, el modal DEBE decirlo con palabras.
- El mensaje de fallo (`RUN_MESSAGES['failed']` y el detalle del JS) DEBE apuntar
  al modal en vez de mandar a "revisa el log del servidor".
- Aceptación: pruebas de render en `apps/dashboard/tests/test_update.py`.

## S6 — Pruebas

`make test-deploy` DEBE incluir `deploy/tests/test_autodeploy_log.sh` (registrado
en `test_shell_scripts.sh`), y `python manage.py test apps.dashboard` DEBE cubrir
el endpoint.

- Aceptación: ambos en verde.

## S7 — Documentación

`deploy/README-deploy.md` DEBE documentar `/var/lib/webcmp/deploy.log`, sus
topes (`DEPLOY_LOG_MAX_BYTES`, `UPDATE_LOG_MAX_BYTES`), el botón del panel y la
fila de permisos en la tabla.

- Aceptación: la sección "Cuando el deploy falla" nombra el botón y el archivo.
