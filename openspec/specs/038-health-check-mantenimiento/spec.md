# 038-health-check-mantenimiento — requisitos

## S1 — El 503 del modo de mantenimiento no revierte

`deploy/deploy.sh` DEBE dar por bueno un 503 cuando
`SiteConfiguration.maintenance_mode` esté encendido y `/login/` responda 2xx o
3xx, e informarlo en el log con la aclaración de que la página pública no se
verifica en esa ventana.

- El resultado DEBE pasar por `health_verdict()`, que es la función que las
  pruebas ejercitan.
- Aceptación: `deploy/tests/test_deploy_sh_health.sh`.

## S2 — El lado cerrado

Sin confirmación de que el 503 venga del modo de mantenimiento, el deploy DEBE
abortar igual que antes. Concretamente DEBE abortar cuando:

- `maintenance_mode` esté apagado;
- la lectura del flag falle (base caída, venv roto, unidad transitoria
  indisponible);
- el flag esté encendido pero `/login/` no responda 2xx o 3xx.

- Aceptación: los casos «apagado», «sin salida», «`/login/` en 000» y
  «`/login/` en 500» del test.

## S3 — Transporte idéntico

`/login/` DEBE consultarse con los mismos argumentos que el health check
principal (`hc_args`), de modo que reutilice `HEALTHCHECK_RESOLVE`,
`HEALTHCHECK_UNIX_SOCKET`, `HEALTHCHECK_HOST_HEADER` e `HEALTHCHECK_INSECURE`.

- La ruta DEBE derivarse de `HEALTHCHECK_URL`: `${hc_url%/}/login/`.
- La pregunta al flag DEBE ir por `manage()`, en la misma unidad transitoria que
  el resto del deploy (`EnvironmentFile`, `PRODUCTION=1`, usuario del sitio), y
  su salida DEBE filtrarse con `grep -qx True` para que la línea de importación
  automática de `manage.py shell` no cuente como resultado.
- Aceptación: el test verifica la URL, el `--resolve` reutilizado y las cinco
  salidas posibles de la pregunta.

## S4 — Sin cambios en el resto de los códigos

2xx, 3xx, `000` (con sus tres mensajes) y cualquier otro código DEBERN
comportarse exactamente como antes.

- Aceptación: los casos `200`, `302`, `000` y `404` del test; `make test-deploy`
  en verde.

## S5 — Documentación

`deploy/README-deploy.md` DEBE documentar en «Health check» qué hace el paso, la
tabla de resultados por código y la razón por la que la ventana de mantenimiento
y la del deploy son la misma ventana.

## S6 — Entrega sin comandos en el servidor

La decisión DEBE vivir en `deploy/deploy.sh`, y la copia root
`/usr/local/sbin/webcmp-deploy` DEBE reinstalarse una sola vez, con el commit ya
desplegado y **antes de la entrega del contenedor**.

- Después de ese paso, ningún camino de este cambio DEBE exigir un comando en el
  servidor: el flag se pregunta y el probe se hace dentro del propio deploy.
- Aceptación: `deploy/tests/test_shell_scripts.sh` verifica la sintaxis del
  script; la reinstalación queda registrada como tarea pendiente en `tasks.md`.
