# 042-dashboard-comercial — propuesta

> **Estado: borrador para revisión.** Primer dashboard por perfil, comenzando por Comercial, con el lenguaje visual de la consola de Monitoreo del sitio.

## 1. Motivación

`DashboardView` (`apps/dashboard/views/dashboard/dashboard.py`) concentra hoy varios dominios en una sola pantalla: KPIs de superusuario, alertas meteorológicas, suscripciones de cliente, resumen comercial y pronósticos. La plantilla `pages/dashboard/index.html` solo incluye parciales condicionados por permisos.

Esto genera dos problemas:

- **Mezcla de dominios**: un usuario con permisos comerciales ve bloques comerciales junto a otros que no son su foco; el dashboard no tiene una narrativa clara por rol.
- **Estilo inconsistente**: el resumen comercial usa tarjetas KPI simples y charts propios, mientras que Monitoreo del sitio (`pages/dashboard/monitoring.html`) tiene un lenguaje visual más sólido (consola de estado, `eyebrow`, `monitoring-figure`, tarjetas con jerarquía, refresco).

## 2. Solución

Crear el primer dashboard por perfil: **Comercial**.

1. **Ruta propia**: `/dashboard/comercial/` con `CommercialDashboardView`, acceso por permisos comerciales (`commercial.view_subscription` o `commercial.view_invoice`) o superusuario/staff con esos permisos; clientes no acceden.
2. **Servicio de datos**: extraer la lógica comercial de `DashboardView`/`build_shared_kpis` a un servicio dedicado (`apps/dashboard/services/commercial_dashboard.py`) que devuelva contexto listo para la plantilla.
3. **Plantilla con estilo consola**: `pages/dashboard/comercial.html` reutiliza primitivas visuales de monitoreo (eyebrow, figure, cards, jerarquía) y muestra KPIs, ingresos, suscripciones y acciones rápidas.
4. **Hub/router**: `dashboard:index` pasa a resolver el dashboard principal del usuario; si tiene un solo perfil claro redirige, si tiene varios muestra hub o mantiene compatibilidad controlada. Comercial es el primer perfil migrado.
5. **CSS compartido**: extraer primitivas reutilizables de monitoreo a `static/dist/css/dashboard-console.css` (o equivalente) sin romper la página de monitoreo.

## 3. Criterios de aceptación

- Existe `/dashboard/comercial/` y aparece en el menú para usuarios con permisos comerciales.
- La vista requiere login y permisos comerciales; usuarios sin permiso reciben 403/redirect según patrón existente.
- El dashboard comercial muestra, como mínimo: ingresos del mes, suscripciones activas/pendientes/solicitadas, gráfico de ingresos, gráfico/estado de suscripciones y accesos rápidos a Comercial.
- Los datos provienen de un servicio dedicado; `DashboardView` deja de ser el único lugar con lógica comercial o la delega.
- El estilo usa el lenguaje visual de monitoreo (eyebrow, monitoring-figure, cards consistentes), responsive y sin regresión en monitoreo.
- `dashboard:index` redirige o enruta a Comercial cuando ese es el perfil principal del usuario, manteniendo compatibilidad para clientes/superusuarios según se defina.
- Pruebas Django para permisos, contexto, routing y render básico.

## 4. Fuera de alcance

- Dashboards de Meteorología, Observaciones, Sistema/Legal/Usuarios (cambios posteriores).
- Rediseño completo de Monitoreo del sitio.
- Nuevas métricas comerciales que requieran modelos nuevos.
- Reemplazo total inmediato del dashboard legacy para todos los roles en el mismo PR, si el riesgo es alto; se permite migración gradual.
