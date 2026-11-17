# 038-health-check-mantenimiento — propuesta

> **Estado: aprobada el 2026-11-17.** El usuario pidió que el health check no
> trate como caída el 503 del modo de mantenimiento, con la premisa de que el
> contenedor se entrega **sin acceso SSH**: todo lo que resuelva este cambio
> tiene que resolverlo el propio deploy, sin comandos manuales en el servidor.

## 1. Motivación

El deploy de v0.7.2 (2026-11-17) revirtió solo: el health check recibió 503 y
abortó con `El sitio responde 503, se esperaba 2xx o 3xx`.

El sitio estaba arriba. Ese 503 lo devolvió `MaintenanceModeMiddleware`
(`apps/core/middleware.py`), que responde la página de mantenimiento a todo
visitante anónimo cuando `SiteConfiguration.maintenance_mode` está encendido y
es la **única** fuente de 503 para `/` en el proyecto.

La ventana de mantenimiento y la del deploy son la misma ventana: **Aplicar
cambios** del panel solo se habilita con el modo de mantenimiento activo
(`apps/core/views/env_config.py`). Un deploy disparado con el flag encendido
revierte siempre, aunque el sitio esté sano, y el operador solo lo descubre
leyendo el journal.

## 2. Solución

`deploy.sh` separa la decisión del curl en `health_verdict()`:

- **2xx o 3xx** → pasa, igual que siempre.
- **503** → pregunta a Django si el modo de mantenimiento está encendido
  (`site_in_maintenance()`, con el mismo `manage` y el mismo transient unit que
  el resto del deploy).
  - **Encendido** → verifica que la aplicación siga atendiendo en `/login/`,
    la única ruta que el middleware deja pasar (`health_probe_login()`), con
    los mismos argumentos de transporte que el health check principal. 2xx o
    3xx → pasa **avisando** de que la página pública no se verifica en esa
    ventana.
  - **Apagado o ilegible** → aborta, como antes.
- **Cualquier otro código** → aborta, como antes.

El lado cerrado es deliberado: sin evidencia de que sea una ventana anunciada,
un 503 sigue siendo una caída.

## 3. Criterios de aceptación

- Un 503 con el flag encendido y `/login/` atendiendo no revierte el deploy, y
  el log del panel lo dice con esas palabras.
- Un 503 con el flag apagado, o con el flag ilegible, revierte.
- Un 503 con el flag encendido pero la aplicación caída (`/login/` sin 2xx/3xx)
  revierte.
- 2xx/3xx, `000` y el resto de los códigos se comportan exactamente como antes.
- `make test-deploy` en verde, con `deploy/tests/test_deploy_sh_health.sh`
  registrado en `deploy/tests/test_shell_scripts.sh`.
- `deploy/README-deploy.md` documenta el comportamiento.

## 4. Límite de entrega

`deploy.sh` vive en el repo, pero el botón **Actualizar** ejecuta la copia root
`/usr/local/sbin/webcmp-deploy`, que no se actualiza sola (si el checkout —
escribible por el usuario del sitio— pudiera reemplazar un script que corre
como root, el botón sería ejecución remota como root).

Este cambio necesita **una** línea de root **antes de la entrega del
contenedor**, y después ninguna: ver `README-deploy.md`, «Cuando el cambio toca
`deploy.sh`».
