# 043-dashboard-meteorologia — requisitos

## S1 — Acceso y ruta
- Existe `GET /dashboard/meteorologia/` con nombre `dashboard:meteorologia`.
- Requiere login; permite superusuario o `meteo.view_forecast` o `meteo.view_warning`.
- Niega sin permisos y no expone a clientes.

## S2 — Datos meteorológicos
- Servicio dedicado calcula contexto; `range` acepta `7d|30d|3m`, inválido cae a default seguro.
- Incluye último pronóstico, series de temperatura, alertas activas y flags de datos disponibles.

## S3 — UI consola
- Usa lenguaje visual consola compartido; muestra alertas, pronóstico y gráfico de temperaturas.
- Estados vacíos claros; responsive; sin regresión en monitoreo/comercial.

## S4 — Routing y compatibilidad
- `dashboard:index` redirige a meteorología cuando es el perfil principal aplicable.
- Menú Dashboard y Meteorología exponen entrada.
- Dashboard legacy no se rompe.

## S5 — Verificación
- Tests Django cubren acceso, routing, normalización, contexto y render.
- `manage.py check`, `ruff`, `djlint` y tests relevantes pasan.
