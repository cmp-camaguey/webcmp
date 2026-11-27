# 044-dashboard-sistema — requisitos

## S1 — Acceso y ruta
- Existe `GET /dashboard/sistema/` con nombre `dashboard:sistema`.
- Requiere login; permite superusuario o `core.view_activitylog`.
- Niega sin permisos y no expone a clientes.

## S2 — Datos operativos
- Servicio dedicado calcula contexto: mantenimiento, tareas, respaldo, usuarios/sesiones.
- Maneja ausencia de datos/estado con defaults seguros.

## S3 — UI consola
- Usa lenguaje visual consola compartido; muestra estado operativo, atención y accesos rápidos.
- Estados vacíos claros; responsive; sin regresión en dashboards existentes.

## S4 — Routing y compatibilidad
- `dashboard:index` enruta compatiblemente. Menús Dashboard y Sistema exponen entrada.
- Dashboard legacy no se rompe.

## S5 — Verificación
- Tests Django cubren acceso, routing, contexto y render.
- `manage.py check`, `ruff`, `djlint` y tests relevantes pasan.
