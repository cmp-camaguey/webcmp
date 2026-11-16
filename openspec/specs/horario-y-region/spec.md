# horario-y-region Specification

Capability: `horario-y-region` (zona horaria y formato de hora del sitio)

## Purpose

El operador elige la zona horaria y el formato de hora desde la misma página de
configuración del sitio, y todas las horas que muestran el portal y el panel
respetan esa elección sin retoques por plantilla. La zona activa nunca se filtra
entre requests del mismo worker.

## Requirements

### Requirement: HORARIO-1 — Sección de configuración

El horario y el formato de hora SHALL vivir en la misma página que el resto de la
configuración del sitio: Configuración → Sitio (`core:site_configuration`). NO
DEBE existir una entrada de menú ni una URL separadas.

#### Scenario: Superusuario con permiso

- GIVEN un superusuario con `core.change_siteconfiguration`
- WHEN abre la página de configuración del sitio
- THEN responde 200 y contiene la tarjeta **Horario y región** con los tres campos
- AND el menú de Configuración no tiene una entrada aparte para el horario
- AND `/config/horario-region/` no existe

#### Scenario: Usuario sin permiso

- GIVEN un usuario autenticado sin `core.change_siteconfiguration`
- WHEN abre la página de configuración del sitio
- THEN responde 403

### Requirement: HORARIO-2 — Modo de zona horaria

La sección SHALL permitir elegir entre `Automático` y `Manual`. `Automático` usa
la zona configurada en el servidor (`settings.TIME_ZONE`); `Manual` usa una
diferencia fija con UTC elegida por el administrador.

#### Scenario: Persistencia y resolución

- GIVEN el operador elige un modo y guarda
- WHEN se consulta el singleton
- THEN el valor persiste
- AND `get_timezone()` devuelve la zona correcta en cada modo

### Requirement: HORARIO-3 — Diferencia manual con UTC

En modo manual SHALL poderse elegir cuántas horas se suman o restan al UTC, entre
−12 y +14.

#### Scenario: Valor fuera de rango

- GIVEN un offset de −13 o +15
- WHEN se envía el formulario
- THEN el formulario lo rechaza y no guarda

#### Scenario: Valor válido

- GIVEN un offset dentro del rango
- WHEN se guarda
- THEN el valor elegido queda persistido

### Requirement: HORARIO-4 — Formato de hora

La sección SHALL permitir elegir formato de 24 horas (`14:30`) o de 12 horas con
AM/PM (`02:30 PM`).

#### Scenario: Formato resuelto

- GIVEN el operador elige 24 o 12 horas
- WHEN se guarda
- THEN el valor persiste
- AND `get_time_format()` devuelve `H:i` o `h:i A` según el caso

### Requirement: HORARIO-5 — Aplicación en las vistas

Las horas mostradas en el portal y en el panel SHALL respetar la zona horaria y el
formato configurados, sin cambios manuales por plantilla.

#### Scenario: Manual con offset negativo y formato de 12 horas

- GIVEN modo `Manual`, offset −3 y formato de 12 horas
- WHEN se renderiza un datetime almacenado en UTC
- THEN se muestra tres horas antes y con AM/PM

### Requirement: HORARIO-6 — Integridad operativa

La zona activa NO DEBE filtrarse entre requests del mismo worker.

#### Scenario: Restauración al terminar el request

- GIVEN un request que activó una zona
- WHEN el request termina
- THEN `timezone.get_current_timezone()` vuelve a `settings.TIME_ZONE`

### Requirement: HORARIO-7 — Pruebas

La suite SHALL cubrir la vista y la plantilla (permiso y tarjeta), el modelo y el
formulario (modos, rango y formato), los filtros de plantilla y el middleware de
zona horaria.
