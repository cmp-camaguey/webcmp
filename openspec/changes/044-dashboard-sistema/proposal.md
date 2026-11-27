# 044-dashboard-sistema — propuesta

## 1. Motivación

Los superusuarios/operadores necesitan una vista rápida del estado operativo del sistema: tareas, respaldos, monitoreo, mantenimiento y actividad de usuarios.

## 2. Solución

Crear dashboard por perfil **Sistema**:

1. **Ruta propia**: `/dashboard/sistema/` con `SystemDashboardView`, nombre `dashboard:sistema`.
2. **Acceso**: superusuario o `core.view_activitylog`. Clientes no acceden.
3. **Servicio de datos**: `apps/dashboard/services/system_dashboard.py` concentra KPIs operativos (mantenimiento, tareas, respaldos, usuarios/sesiones).
4. **UI consola**: reutiliza `dashboard-console.css`; muestra estado operativo, atención, tareas, respaldos y accesos rápidos.
5. **Router/menú**: `dashboard:index` redirige a sistema cuando aplique; menú Dashboard y Sistema exponen la entrada.

## 3. Criterios de aceptación

- Existe `/dashboard/sistema/` con nombre `dashboard:sistema`.
- Requiere login; permite superusuario o `core.view_activitylog`; niega sin permisos y a clientes.
- Muestra estado operativo útil: mantenimiento, tareas, respaldos, usuarios/sesiones, accesos rápidos.
- Usa estilo consola compartido y no rompe dashboards existentes.
- `dashboard:index` enruta compatiblemente; menús exponen acceso.
- Tests Django, `check`, `ruff`, `djlint` verdes.

## 4. Fuera de alcance

- Cambios en páginas de monitoreo/tareas/respaldos existentes.
- Nuevas métricas de infraestructura.
