# 043-dashboard-meteorologia — diseño

## Contexto

Legacy dashboard ya calcula: `latest_forecast`, forecast series (`_build_forecast_series`), latest alerts (`_build_alerts_block`) y flags `show_forecast/show_alerts`. Plantillas: `includes/dashboard/pronosticos.html`, `includes/dashboard/alertas_activas.html`. Chart temperatura usa `#temperatureTrendChart` y `dashboard.js`.

## Diseño

### Ruta y acceso
- `/dashboard/meteorologia/` → `MeteoDashboardView`, name `dashboard:meteorologia`.
- `has_meteo_dashboard_access(user)`: autenticado, no cliente, y `is_superuser or has_perm('meteo.view_forecast') or has_perm('meteo.view_warning')`.

### Servicio
`apps/dashboard/services/meteo_dashboard.py`:
- `normalize_range(range)` acepta `7d|30d|3m`, default `7d`.
- `get_meteo_dashboard_context(*, range='7d')` devuelve latest forecast, forecast series, latest alerts, counts/flags, rango seleccionado.
- Reusa lógica de `dashboard.py` (extraer/importar helpers) para no duplicar.

### UI
`pages/dashboard/meteorologia.html`, estilo consola:
- Header Dashboard/Meteorología + acciones rápidas (Pronósticos, Avisos).
- Console/KPI: fecha último pronóstico, cantidad avisos activos, rango.
- Alertas activas (reusar parcial o bloque equivalente).
- Pronóstico por regiones + gráfico temperaturas (reusar parcial/JS existente).
- Estados vacíos.

### Router/menú
- `dashboard:index`: cliente -> legacy; superuser -> legacy; commercial-only staff -> commercial; meteo-only staff -> meteorologia; fallback legacy.
- Menú Dashboard dropdown agrega “Meteorología”.
- Menú Meteorología agrega “Resumen meteorológico”.

### Pruebas
- Acceso/ruta, router, contexto/normalización rango, render con/sin datos, regresión comercial/index.
