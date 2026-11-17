# 038-health-check-mantenimiento — diseño

## 1. Por qué leer el flag y no aceptar todo 503

Aceptar cualquier 503 como «arriba» es una línea, y es el cambio más barato.
También es el que peor envejece: el health check es la única puerta que decide
si un deploy revierte, y con esa regla cualquier 503 futuro —una vista nueva,
un throttle, un proxy— pasaría como deploy sano. El check dejaría de
distinguir «el sitio responde» de «hay algo roto», que es lo único que existe
para.

La otra opción, leer `SiteConfiguration.maintenance_mode`, responde la
intención del operador con precisión: el flag es la causa, no una conjetura
sobre el código HTTP. Lo que no alcanza por sí solo es evidencia de que la
aplicación atienda: el flag puede estar encendido y el sitio igual roto.

Por eso hacen las dos cosas. El flag decide **si** vale la pena seguir mirando;
`/login/` decide si la aplicación **está atendiendo**.

## 2. Por qué `/login/` y no otra ruta

`MaintenanceModeMiddleware` deja pasar exactamente dos paths: `login` y
`logout`. Es una decisión del propio middleware, documentada en su comentario:
«an anonymous visitor (or a just-logged-out admin) must be able to log in to
restore the site».

`/login/` es la que sirve para eso, y además renderiza plantilla, toca la base
(sesiones) y pasa por todo el stack. Si `/login/` contesta 2xx o 3xx, la
aplicación está arriba; si no, el problema no es el modo de mantenimiento.

Se arma con los mismos `hc_args` que el health check principal, así que reutiliza
`--resolve`, `--unix-socket`, el `Host:` y `--insecure` del `deploy.env`: mismo
proxy, mismo TLS, mismo recorrido. Solo cambia la URL.

## 3. Por qué la pregunta va por `manage`

`manage()` ya existe en el script y ya se usa en el paso 7 (`migrate --check`).
Corre en un transient unit con `EnvironmentFile=/etc/webcmp/encryption.env`,
`PRODUCTION=1` y el usuario del sitio: es la única forma de que `manage.py`
vea la configuración real. Un `sudo -u webcmp manage.py` a secas caería al
perfil equivocado.

La salida se filtra con `grep -qx True`: `manage.py shell -c` imprime antes la
línea de importación automática, y `-x` exige que la línea sea exactamente
`True`, así un `True` colgado de un traceback no confirma nada.

Si la lectura falla —base caida, venv roto, systemd-run indisponible— el
resultado es «no se pudo confirmar» y se aborta. Es el mismo lado cerrado de
siempre: sin evidencia de ventana anunciada, un 503 es una caída.

## 4. Dónde vive la decisión

`health_verdict()` queda en su propio bloque `TEST-BLOCK: health-verdict`, como
las demás piezas que este script expone a las pruebas. El flujo del deploy no
cambia: un `curl` y una llamada. La función recibe el código y decide; las
pruebas la ejercitan sin tocar la red ni el sistema, sustituyendo `manage`,
el probe y la salida.

El costo extra solo se paga en el camino que hoy revierte: un deploy que
responde 2xx o 3xx no pregunta nada ni hace un curl más.

## 5. Qué no cambia

- El transporte, los cuatro parámetros `HEALTHCHECK_*` y su validación.
- Los mensajes del `000` (certificado autofirmado, socket, proxy externo).
- El rollback: `die` sale con 1 y la trampa `EXIT` sigue armada hasta después
  del health check, igual que antes.
- El resto de los códigos (`404`, `500`, `*`): mismo aborto, mismo mensaje.

## 6. Límite de entrega

La decisión vive en `deploy.sh`, que es el archivo que el botón **Actualizar**
no puede actualizar solo (ver `README-deploy.md`, «Cuando el cambio toca
`deploy.sh`»). El cambio es inútil en un servidor hasta que la copia root se
reinstale, así que ese paso es **previo a la entrega del contenedor**: después
de él, ningún camino de este fix necesita un comando en el servidor.
