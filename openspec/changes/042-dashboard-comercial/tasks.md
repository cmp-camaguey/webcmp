# 042-dashboard-comercial — tareas

- [x] 1. **Servicio comercial**: crear `apps/dashboard/services/commercial_dashboard.py` con normalización de `income_range`, KPIs, series de ingresos y conteos/listas de suscripciones. Cubrir con tests.
- [x] 2. **Extracción CSS consola**: crear `static/dist/css/dashboard-console.css` con primitivas reutilizables (`eyebrow`, `figure`, `console`, `card`, `chart`) y adaptar `monitoring.html` para incluirlo sin regresión visual/funcional.
- [x] 3. **Vista y ruta**: agregar `CommercialDashboardView`, URL `dashboard/comercial/`, permiso `has_commercial_dashboard_access`, y nombre `dashboard:commercial`.
- [x] 4. **Template comercial**: crear `pages/dashboard/comercial.html` con estilo consola, KPIs, charts, tabla/lista de atención y acciones rápidas.
- [x] 5. **Menú y router**: agregar acceso en menú Comercial/Dashboard; adaptar `dashboard:index` como router compatible con los perfiles existentes.
- [x] 6. **Migración legacy**: hacer que el bloque comercial del dashboard legacy use el servicio compartido o eliminar duplicación controlada.
- [x] 7. **Pruebas**: permisos, router, contexto del servicio, render, regresión de dashboard legacy y monitoreo.
- [x] 8. **Docs/verificación**: actualizar docs si aplica, correr `ruff`, `djlint`, `manage.py check`, tests de `apps.dashboard` y relevantes.
