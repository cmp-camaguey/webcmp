# 3 · Monitoreo

Qué mide la app `apps/monitoring`, de dónde salen los datos, cuánto se guardan y
qué rompe si se toca.

## Qué mide

Dos familias que no se mezclan:

| Origen | Modelo | Qué registra |
| --- | --- | --- |
| Middleware del servidor | `RequestMetric` | Una fila por petición: método, ruta, código y duración del backend |
| Beacon del navegador | `PageView` | Ruta, referrer, dispositivo, navegador, sistema, peso y recursos lentos |
| Beacon del navegador | `WebVital` | LCP, FCP, INP aproximado y CLS |
| Beacon del navegador | `JavaScriptError` | Excepción, origen y línea (máximo 5 por página) |

Los recursos del servidor (CPU, memoria, disco) no se guardan: se leen con
`psutil` en el momento de renderizar la página. Si `psutil` falla, el campo queda
vacío y la página sigue respondiendo.

## Quién lo ve

`/dashboard/monitoring/` (`dashboard:monitoring`) y su endpoint de datos
(`dashboard:monitoring_data`) exigen sesión y superusuario. La entrada del menú
vive en `templates/includes/dashboard/menu/_dashboard.html`.

## El beacon

`static/dist/js/rum-beacon.js` envía los eventos a `POST /rum/collect/`
(`monitoring:rum_collect`). Es la única entrada sin sesión porque la visitan
también las páginas públicas, y por eso el contrato es cerrado:

- cuerpo máximo de 8 KB, rechazado antes de parsear;
- JSON de un solo objeto con `kind` en `pageview`, `vitals` o `error`;
- sesión anonimizada con un hash SHA-256 truncado a 32 caracteres;
- throttling por sesión y tipo de evento (2 s; 5 s para errores);
- respuesta 204 o un código de rechazo sin cuerpo: un visitante anónimo no puede
  descubrir el esquema interno.

Si se agrega un `kind`, hay que tocar la lista blanca de `apps/monitoring/views.py`
y el JS a la vez.

## Retención y poda

| Variable | Por defecto | Qué poda |
| --- | --- | --- |
| `MONITORING_HTTP_RETENTION_DAYS` | 14 | `RequestMetric` |
| `MONITORING_RETENTION_DAYS` | 30 | `PageView`, `WebVital`, `JavaScriptError` |

La lógica vive en `apps/monitoring/prune.py` y la usan dos entradas: la tarea
periódica `podar_monitoreo` (Huey, 04:30 UTC) y el comando manual:

```bash
python manage.py prune_monitoring
```

`MonitoringConfig.ready()` importa `apps.monitoring.tasks`; ese import es lo que
registra el `crontab` en Huey. Si se borra, la poda deja de existir sin que nada
falle a la vista.

## Interruptor

`MONITORING_ENABLED` (por defecto `True`) apaga todo el monitoreo. El perfil
`testing` lo desactiva para que la suite no escriba métricas; los tests que
prueban el monitoreo lo reactivan con `override_settings(MONITORING_ENABLED=True)`.

## Qué rompe si se cambia

- **El orden del middleware.** `RequestMetricsMiddleware` va justo después de
  WhiteNoise: los estáticos salen antes y no ensucian la muestra. Moverlo cambia
  lo que se mide.
- **El nombre del endpoint.** El JS apunta a `/rum/collect/` literal; renombrar
  la ruta rompe el beacon sin error visible.
- **La poda.** Ver arriba: sin el import en `ready()` no hay error, solo datos que
  crecen.
- **El contrato del beacon.** El endpoint es público; quitar el límite de cuerpo o
  el throttling lo deja como escritura anónima sin freno.

Pruebas: `python manage.py test apps.monitoring`.
