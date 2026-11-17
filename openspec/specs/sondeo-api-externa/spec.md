# sondeo-api-externa Specification

Capability: `sondeo-api-externa` (sondeo vertical servido por la API externa de modelos)

## Purpose

El sondeo vertical y su exportación los resuelve una API externa
(`modelo.cmw.insmet.cu`); el portal solo reenvía la petición y conserva el
contrato que consume `sounding.js`. El generador local de gráficos y sus
dependencias salieron del repositorio.

## Requirements

### Requirement: SONDEO-1 — Sondeo servido por la API externa

`SoundingView.post` SHALL reenviar la petición a
`https://modelo.cmw.insmet.cu/api/sounding/` con `datetime_init`, `lat`, `long`
del municipio seleccionado y `t_index` en base 0.

#### Scenario: API disponible

- GIVEN la API externa responde
- WHEN se hace `POST /modelo/sounding/`
- THEN devuelve 200
- AND la vista NO importa `matplotlib` ni `apps.home.data.plot_generators`

### Requirement: SONDEO-2 — Contrato del gráfico

La respuesta SHALL conservar
`{"status": "success", "plot_image": "<base64>", "datetime": ..., "params": ...}`,
que consume `static/dist/js/sounding.js`, tanto si la API responde el PNG en crudo
como si responde un sobre JSON con `plot_image`/`image`.

#### Scenario: PNG en crudo y base64

- GIVEN la API responde un PNG en crudo en un caso y base64 en JSON en el otro
- WHEN el portal los procesa
- THEN ambos producen el mismo `plot_image`

### Requirement: SONDEO-3 — Errores del sondeo

Formulario inválido → 400 con `errors`. API 404 → 404 con mensaje de «sin datos».
Sin conexión, 5xx o respuesta sin gráfico → 502 con `message`.

#### Scenario: Cada camino de error

- GIVEN la API simulada en cada uno de esos estados
- WHEN se hace la petición
- THEN el código y el cuerpo corresponden al caso

### Requirement: SONDEO-4 — Exportación

`SoundingExportView` SHALL pedir el archivo a la API externa reenviando `fmt` y
servirlo con `Content-Type` del formato y
`Content-Disposition: attachment; filename="sounding_<stamp>.<fmt>"`. Un `fmt`
fuera de `{png, pdf, svg}` SHALL responder 400 sin llamar a la API.

#### Scenario: Exportar PDF

- GIVEN `fmt=pdf`
- WHEN se descarga el sondeo
- THEN se entrega `application/pdf` como adjunto

#### Scenario: Formato no soportado

- GIVEN `fmt=gif`
- WHEN se descarga el sondeo
- THEN responde 400 y no se llama a la API

### Requirement: SONDEO-5 — Retiro del generador local

`apps/home/data/plot_generators.py` y `apps/home/tests/test_skewt_export.py`
SHALL salir del repositorio, con una copia sin versionar para reutilizarse al
escribir la API externa. `MetPy` y `matplotlib` SHALL salir de
`requirements/base.txt`.

#### Scenario: Repositorio sin el generador

- GIVEN el árbol de trabajo
- WHEN se ejecuta `git ls-files`
- THEN no lista esos dos archivos
- AND la copia local existe sin versionar
- AND la suite pasa sin MetPy ni matplotlib

### Requirement: SONDEO-6 — Rutas de `/modelo/`

Las rutas de sondeo SIGUEN comentadas mientras la API externa esté caída, y
`modelo/descargar_gif/` SHALL quedar comentada como las demás, igual que su
referencia en `maps.html`.

#### Scenario: Ninguna ruta activa

- GIVEN el `urls.py` de `/modelo/`
- WHEN se inspecciona
- THEN ninguna ruta de sondeo está activa
- AND `manage.py check` no reporta errores de plantilla
