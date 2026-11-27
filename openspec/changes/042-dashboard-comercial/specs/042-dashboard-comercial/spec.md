# 042-dashboard-comercial — requisitos

## S1 — Acceso y ruta
- Existe `GET /dashboard/comercial/` con nombre `dashboard:commercial`.
- Requiere usuario autenticado.
- Permite acceso a superusuario o usuario con `commercial.view_subscription` o `commercial.view_invoice`.
- Niega acceso a usuarios sin permisos comerciales (403 o patrón existente del dashboard).
- No expone datos comerciales a clientes.

## S2 — Datos comerciales
- Un servicio dedicado calcula el contexto del dashboard comercial.
- `income_range` acepta `1m`, `3m`, `6m`, `12m`, `all`; valores inválidos caen a default seguro.
- Incluye ingresos del mes, series facturado/cobrado por rango, y conteos de suscripciones `paid`, `pending`, `requested` con `record_active=True`.
- Listas de drill-down están limitadas y ordenadas de forma estable.

## S3 — UI estilo consola
- La plantilla usa el lenguaje visual de monitoreo: jerarquía de consola, `eyebrow`, cifras `figure`, tarjetas consistentes y responsive.
- Muestra KPIs, gráfico de ingresos, estado de suscripciones y accesos rápidos a áreas comerciales.
- No introduce regresiones visuales/funcionales en `/dashboard/monitoring/`.

## S4 — Routing y compatibilidad
- `dashboard:index` actúa como router/hub compatible: preserva acceso válido existente y redirige a `dashboard:commercial` cuando el perfil comercial es el principal aplicable.
- El menú expone el dashboard comercial a usuarios con permiso.
- El dashboard legacy no se rompe para roles aún no migrados.

## S5 — Verificación
- Tests Django cubren permisos, routing, normalización de rango, contexto y render.
- `manage.py check`, `ruff`, `djlint` y tests relevantes pasan.
