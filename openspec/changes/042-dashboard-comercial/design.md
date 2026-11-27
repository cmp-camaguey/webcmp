# 042-dashboard-comercial — diseño

## Contexto actual

- `DashboardView` (`apps/dashboard/views/dashboard/dashboard.py`): arma contexto por flags `show_commercial`, `show_forecast`, `show_alerts`, `is_client`, `is_superuser`. Comercial calcula `month_income`, conteos de suscripciones, listas y datos de charts; usa `build_shared_kpis`.
- `templates/pages/dashboard/index.html`: incluye parciales por dominio.
- `templates/includes/dashboard/resumen_comercial.html`: KPIs + chart ingresos + chart suscripciones + modal detalle.
- `templates/pages/dashboard/monitoring.html`: estilo consola con CSS inline (`monitoring-console`, `monitoring-eyebrow`, `monitoring-figure`, `monitoring-card`, tracking slots) y tarjetas operativas.
- Roles/permisos: `apps/user_auth/roles.py` define módulo `Comercial`; permisos modelo `commercial.view_*`.

## Diseño

### 1. Rutas y vistas

| Ruta | Vista | Nombre | Acceso |
| --- | --- | --- | --- |
| `/dashboard/` | `DashboardRouterView` o `DashboardView` adaptada | `dashboard:index` | login; redirige al perfil principal o renderiza hub legacy |
| `/dashboard/comercial/` | `CommercialDashboardView` | `dashboard:commercial` | login + permiso comercial |

**Permiso comercial**: `has_commercial_dashboard_access(user)` devuelve `user.is_superuser or user.has_perm('commercial.view_subscription') or user.has_perm('commercial.view_invoice')`. Clientes (`Clientes` group sin rol staff comercial) no entran.

**Router `dashboard:index`**:
- cliente -> comportamiento actual de cliente (o redirección dedicada si ya existe);
- acceso comercial y sin otro dashboard principal más específico -> redirect `dashboard:commercial`;
- superusuario sin preferencia clara -> puede ir a comercial/sistema o mantener hub; primera iteración: conservar compatibilidad, redirigir a comercial solo si es su único perfil operativo y no superusuario puro.
- fallback: vista actual.

La primera iteración debe evitar romper accesos existentes. Se documentará la matriz de redirección en tests.

### 2. Servicio de datos

Crear `apps/dashboard/services/commercial_dashboard.py`:

```python
def get_commercial_dashboard_context(user, *, income_range='12m') -> dict: ...
```

Responsabilidades:
- validar/normalizar `income_range` (`1m`, `3m`, `6m`, `12m`, `all`);
- calcular ingresos del mes, ingresos por rango, facturados/cobrados;
- contar suscripciones `paid/pending/requested` con `record_active=True`;
- obtener listas recientes para drill-down (limitadas, p. ej. 20);
- devolver datos ya serializados para charts donde convenga;
- no depender de `request`; la vista pasa parámetros.

`DashboardView` puede delegar en este servicio para no duplicar lógica durante la migración. La meta final es que la lógica comercial viva en un solo lugar.

### 3. Plantilla

`apps/dashboard/templates/pages/dashboard/comercial.html` (o `commercial.html`, mantener convención del proyecto):

- extiende `layouts/dashboard.html`.
- cabecera tipo consola: `page-pretitle` Dashboard, `h2` Comercial, acciones rápidas (Nueva factura, Suscripciones, Clientes).
- fila de KPIs con estilo consola: tarjeta principal/eyebrow/figure o tarjetas compactas con `monitoring-figure`.
- sección de gráficos: ingresos por rango y distribución/estado de suscripciones.
- tabla/lista de atención: pendientes/solicitadas recientes o últimas facturas.
- estado vacío cuando no hay datos.

**No se copia el bloque inline completo de monitoreo**. Se extraen primitivas CSS comunes.

### 4. CSS compartido

Crear `static/dist/css/dashboard-console.css` con primitivas tomadas de `monitoring.html`:

- `.dashboard-eyebrow` / alias compatible con `.monitoring-eyebrow`.
- `.dashboard-figure`.
- `.dashboard-console` (borde superior, jerarquía).
- `.dashboard-card` con `card-body` flex.
- utilidades de chart alto (`.dashboard-chart`).

Estrategia:
1. Mover clases genéricas a `dashboard-console.css`.
2. En `monitoring.html`, mantener compatibilidad: incluir nuevo CSS y dejar alias o reemplazar clases gradualmente. Primera iteración puede incluir ambos nombres para evitar regresión.
3. Comercial usa las clases nuevas.

No tocar comportamiento JS de monitoreo.

### 5. Menú

Actualizar `templates/includes/dashboard/menu/_dashboard.html` o el menú Comercial:

- Agregar entrada “Dashboard Comercial” visible con permiso comercial, o convertir “Dashboard” en dropdown por perfiles.
- Mantener acceso simple: si solo hay un dashboard, un link directo; si hay varios, submenú.

La primera iteración puede agregar un enlace en el bloque Comercial: “Resumen comercial” -> `dashboard:commercial`, y dejar `dashboard:index` como router.

### 6. Compatibilidad

- El dashboard legacy sigue funcionando mientras existan roles no migrados.
- `resumen_comercial.html` puede seguir incluyéndose en legacy hasta retirar el bloque; idealmente pasa a usar servicio/partial compartido.
- URLs antiguas no se rompen: `dashboard:index` sigue existiendo.

### 7. Pruebas

- Permisos: anónimo redirige a login; sin permiso comercial 403; con `view_subscription` o `view_invoice` 200; superusuario 200.
- Router: usuario comercial va a comercial; cliente conserva comportamiento; superusuario definido por matriz.
- Contexto: servicio devuelve claves esperadas, normaliza rango, no incluye suscripciones inactivas.
- Template: renderiza KPIs y contenedores de charts.
- Regresión: `dashboard:index` para casos existentes no 500.

## Riesgos

- **Duplicación temporal** durante migración entre legacy y nuevo dashboard. Mitigar con servicio compartido.
- **Router rompe expectativas** de usuarios con varios roles. Mitigar con matriz explícita y tests.
- **Extracción CSS** puede afectar monitoreo. Mitigar moviendo solo primitivas visuales y probando `/dashboard/monitoring/`.
