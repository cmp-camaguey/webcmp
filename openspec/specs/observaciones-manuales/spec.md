# observaciones-manuales Specification

Capability: `observaciones-manuales` (captura manual de observaciones sinópticas e intermedias)

## Purpose

Cada estación captura a mano sus observaciones sinópticas e intermedias, el
sistema genera el telegrama `AAXX` que consume el mapa y queda registro de quién
lo hizo. La visibilidad está restringida por estación y el modo automático por FTP
desactiva la captura manual.

## Requirements

### Requirement: OBS-1 — Interruptor de modo en el panel

`Configuración → Entorno del servidor → Observaciones (FTP)` SHALL incluir el
interruptor **Observaciones automáticas por FTP** (`OBS_AUTOMATIC`), editable y
sujeto a la regla general del panel: se escribe en el archivo de entorno, aplica al
reiniciar y se marca como pendiente mientras difiera.

#### Scenario: Guardar el interruptor

- GIVEN la tarjeta `Observaciones (FTP)` abierta
- WHEN se guarda un cambio de `OBS_AUTOMATIC`
- THEN se agrega o cambia esa clave sin tocar el resto del archivo

### Requirement: OBS-2 — Sección Observaciones

El dashboard SHALL exponer una sección **Observaciones** con entrada propia en el
menú lateral, registro en `/meteo/observaciones/` (`meteo:observacion_list`) y alta
en `/meteo/observaciones/crear/` (`meteo:observacion_create`).

#### Scenario: Con permiso

- GIVEN un usuario con `meteo.view_observation`
- WHEN abre el dashboard
- THEN ve la entrada y la lista responde 200

#### Scenario: Sin permiso

- GIVEN un usuario sin `meteo.view_observation`
- WHEN entra a la sección
- THEN recibe 403 y no ve la entrada en el menú

### Requirement: OBS-3 — Formulario por tipo de observación

El formulario SHALL capturar una observación **Sinóptica** (horas 00/06/12/18, con
temperatura máxima, mínima y precipitación de 24 h) o **Intermedia** (03/09/15/21,
sin esos tres datos).

La hora SHALL pertenecer al tipo elegido; una combinación inválida no guarda. En
sinóptica, máxima y mínima son obligatorias y la mínima no puede superar a la
máxima.

#### Scenario: Hora que no pertenece al tipo

- GIVEN tipo intermedio y hora 12
- WHEN se envía el formulario
- THEN no guarda

#### Scenario: Mínima mayor que la máxima

- GIVEN una sinóptica con mínima 30 y máxima 20
- WHEN se envía el formulario
- THEN se rechaza

### Requirement: OBS-4 — Telegrama y archivo del mapa

Al guardar, el sistema SHALL generar un telegrama `AAXX` decodificable por
`Descodificador` y escribirlo en `MEDIA_ROOT/obs` como `SM{NN}.{HH}` o
`SI{NN}.{HH}` según el tipo. El día embebido SHALL ser el de
`synop_expected_obs_date(hour)`.

#### Scenario: Consulta del ciclo vigente

- GIVEN una observación guardada
- WHEN se consulta `station/observation/<hora>/<estación>/`
- THEN devuelve los valores ingresados para el ciclo vigente

### Requirement: OBS-5 — Personal y visibilidad por estación

La pertenencia SHALL resolverse con grupos de Django `Estacion <número> - <rol>`
(`Jefe`, `Revisor`, `Observador`).

Un usuario SHALL ver solo las observaciones de las estaciones a las que pertenece;
el superusuario ve todas. El detalle, la edición y la eliminación de una
observación de otra estación SHALL responder 404. El formulario SHALL ofrecer solo
las estaciones propias.

#### Scenario: Observación de otra estación

- GIVEN un observador de la estación 5 y una observación de la estación 7
- WHEN abre el detalle, la edición o la eliminación
- THEN recibe 404

### Requirement: OBS-6 — Roles y permisos

Los grupos SHALL otorgar permisos del modelo `Observation`: observador
`view_observation` y `add_observation`; revisor además `change_observation`; jefe
además `delete_observation`. El comando `create_observation_groups` SHALL crear los
18 grupos y agregar los permisos sin quitarlos.

#### Scenario: Comando idempotente

- GIVEN grupos ya creados con permisos
- WHEN se vuelve a ejecutar `create_observation_groups`
- THEN los 18 grupos existen
- AND los permisos previos siguen ahí

### Requirement: OBS-7 — Registro de autoría

El registro SHALL mostrar por observación la estación, el tipo, el día, la hora,
la temperatura, la precipitación de 3 h, el usuario que la realizó y la última
actualización. El detalle SHALL mostrar todos los datos y el telegrama generado.

#### Scenario: Fila del registro

- GIVEN una observación guardada
- WHEN se abre el registro
- THEN la fila muestra los campos de autoría y medición

### Requirement: OBS-8 — Modo automático en consulta

Con `OBS_AUTOMATIC` encendido, la sección NO DEBE permitir crear, editar ni
eliminar; SHALL mostrar un aviso de que las observaciones llegan por FTP.

#### Scenario: Modo automático activo

- GIVEN `OBS_AUTOMATIC` encendido
- WHEN se abre la sección
- THEN el alta, la edición y la eliminación no están disponibles
- AND se muestra el aviso del modo FTP

### Requirement: OBS-9 — Auditoría y archivos

Alta, edición y eliminación SHALL registrar `ActivityLog` con usuario, IP y la
estación/hora afectada. Eliminar SHALL borrar también el telegrama. Editar SHALL
conservar el autor original y reescribir el telegrama.

#### Scenario: Eliminar una observación

- GIVEN una observación con su telegrama en disco
- WHEN se elimina
- THEN el archivo desaparece
- AND queda una entrada de `ActivityLog`

### Requirement: OBS-10 — Pruebas

La suite SHALL cubrir el codificador (ida y vuelta por `Descodificador`, ambos
tipos), el formulario, la unicidad, el alcance por estación, los permisos por rol,
la escritura y el borrado del archivo, el campo del panel y el modo manual en
`FileObs`/API.
