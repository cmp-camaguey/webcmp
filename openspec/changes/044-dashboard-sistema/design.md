# 044-dashboard-sistema — diseño

## Ruta y acceso
- `/dashboard/sistema/` → `SystemDashboardView`, name `dashboard:sistema`.
- `has_system_dashboard_access(user)`: autenticado, no cliente, y `is_superuser or has_perm('core.view_activitylog')`.

## Servicio
`apps/dashboard/services/system_dashboard.py`:
- `get_system_dashboard_context(user)` devuelve maintenance_mode, task counts (error, stale, executing, enqueued, recent), backup status summary, user/session stats, quick flags.

## UI
`pages/dashboard/sistema.html`, consola:
- Estado operativo (mantenimiento, tareas con error, respaldo).
- Atención: errores/stale/backup fallido/mantenimiento activo.
- Tarjetas: tareas, respaldo, usuarios/sesiones.
- Accesos rápidos a Monitoreo, Tareas, Respaldo BD, Entorno, Auditoría.

## Router/menú
- `dashboard:index`: añadir sistema en routing por perfil (superuser sigue viendo legacy por ahora? o sistema-only). Mantener fallback legacy.
- Dashboard dropdown agrega “Sistema”.
- Menú Sistema agrega “Resumen del sistema”.

## Pruebas
- Acceso/ruta, router, contexto, render con/sin datos, regresión.
