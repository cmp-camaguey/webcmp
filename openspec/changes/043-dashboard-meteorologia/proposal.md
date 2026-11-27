# 043-dashboard-meteorologia — propuesta

> **Estado: borrador para revisión.** Segundo dashboard por perfil: Meteorología, con el lenguaje visual de la consola del dashboard.

## 1. Motivación

El dashboard legacy mezcla pronósticos y avisos con bloques comerciales y de sistema. Los usuarios meteorológicos necesitan una vista enfocada en el estado operativo: último pronóstico, alertas activas y tendencia de temperaturas.

## 2. Solución

Crear dashboard por perfil **Meteorología**:

1. **Ruta propia**: `/dashboard/meteorologia/` con `MeteoDashboardView`, nombre `dashboard:meteorologia`.
2. **Acceso**: superusuario o usuario con `meteo.view_forecast` o `meteo.view_warning`. Clientes no acceden.
3. **Servicio de datos**: `apps/dashboard/services/meteo_dashboard.py` concentra contexto meteorológico (último pronóstico, series de temperatura, alertas activas).
4. **UI consola**: reutiliza `dashboard-console.css`; muestra KPIs/estado, alertas activas, resumen del último pronóstico y gráfico de temperaturas.
5. **Router/menú**: `dashboard:index` redirige a meteorología cuando es el perfil principal aplicable; Dashboard y menú Meteorología exponen la entrada.

## 3. Criterios de aceptación

- Existe `/dashboard/meteorologia/` con nombre `dashboard:meteorologia`.
- Requiere login; permite superusuario o `meteo.view_forecast`/`meteo.view_warning`; niega sin permisos y a clientes.
- Muestra último pronóstico, alertas activas y gráfico de temperaturas, con estado vacío cuando no hay datos.
- Usa estilo consola compartido y no rompe monitoreo/dashboard comercial.
- `dashboard:index` enruta compatiblemente; menú Dashboard/Meteorología expone acceso.
- Tests Django cubren permisos, routing, contexto y render. `check/ruff/djlint/tests` verdes.

## 4. Fuera de alcance

- Dashboard de Observaciones/Sistema.
- Cambios al flujo de edición de pronósticos/avisos.
- Nuevas fuentes de datos meteorológicas.
