# 039-version-y-log-vivo — diseño

## 1. Por qué un tag exacto y no «el tag más cercano»

Un release en este repo es un tag que apunta al commit mergeado en `main`:
`git tag -a v0.7.3` se crea sobre `dd1a59c` y ahí termina. Esa es la única
relación que tiene sentido operativo: «el servidor está en v0.7.3» significa
que sirve exactamente el commit que el tag nombra.

Un tag «más cercano» (el último cuyo SHA esté antes en la historia) mentiría
en los dos sentidos que importan: en un hotfix sin tag diría que la versión
más vieja sigue pendiente, y tras un revert diría una versión que ya no está
servida. Preferir la exactitud y, sin tag exacto, no mostrar versión es el
mismo lado cerrado de siempre: sin evidencia, no se afirma.

## 2. Cómo se piden los tags

`_ls_remote()` ya corre un `git ls-remote <repo> <ref>`. Se amplía a dos
refs en una sola llamada — `refs/heads/main` y `refs/tags/*` — así el costo de
red no cambia y el cache de `REMOTE_CACHE_KEY` sigue siendo una sola pieza.

`ls-remote` devuelve dos líneas por tag anotado: `refs/tags/vX` y su peeled
`refs/tags/vX^{}` (el commit real). El peeled es el que se compara contra el
SHA: un tag ligero no trae `^{}` y su propio SHA es el commit. El parseo
descarta cualquier cosa que no tenga forma de SHA y cualquier ref que no sea
tag.

La preferencia entre varios tags apuntando al mismo commit es determinista y
se prueba: `v*` primero (un tag `release-nota` no debería etiquetar la
versión del chip), y entre `v*` el estable (`v1.2.3`) antes que el prerelease
(`v1.2.3-rc.1`).

## 3. Dónde vive la regla

`_version_for(sha, tags)` es una función pura: recibe el SHA y el dict de
tags parseado, devuelve el nombre del tag o `None`. Las pruebas la ejercitan
sin tocar red ni git. `_ls_remote()` pasa a devolver `{'sha', 'tags', 'error'}`,
y `remote_sha()` sigue cacheando ese payload entero.

En `build_state()` se calculan dos valores:

- `deployed_version` = `_version_for(deployed, tags)` — el chip.
- `version` = `_version_for(remote_sha, tags)` — a dónde se actualiza.

Ambos llegan al navegador como string o `None`; el JS decide el texto.

## 4. El chip, el botón y el detalle

El chip es un nodo nuevo en el dropdown (`update-navbar-version`), pintado
con `textContent`. Estados del menú:

- **available**: chip con la versión remota (o el SHA corto si no hay tag);
  botón «Actualizar a vX.Y.Z» si hay versión, «Actualizar ahora» si no;
  detalle «Instala vX.Y.Z (sha)…» o, sin versión, el rango de SHA de siempre.
- **up_to_date**: chip con la versión instalada; el mensaje ya dice el SHA,
  se le apoya el nombre de la versión.
- **running / failed / ok**: el chip muestra la versión que se está
  instalando o la que quedó servida cuando consta; sin versión se queda con
  el SHA, como hoy.
- **unknown**: sin chip de versión que mostrar si no hay tag exacto, o el
  último tag exacto conocido si lo hay — nunca un número inventado.

La cadena de versión jamás se compone en el servidor con formato propio: el
tag ya trae su `v`, el JS lo pega tal cual.

## 5. El log en vivo sin SSE

No hay WebSocket ni SSE en el proyecto, y no hace falta: el polling de estado
ya corre a 2 s durante `running`. El cambio es que, con el modal abierto,
cada respuesta del polling dispare también una lectura del log.

Condiciones, todas del lado del navegador:

- **Modal abierto**: el listener de `show.bs.modal` ya llama `loadLog`; ahora
  se marca `logOpen` en `show`/`hidden` y se limpia al cerrar.
- **Solo `running`**: fuera de `running` no se relee en el ciclo — un
  `up_to_date` rellegiría el archivo cada 60 s para nada. Al salir de
  `running` (ok/failed) se hace **una última** lectura, que es la que trae el
  resultado final.
- **Autoscroll condicional**: antes de reemplazar el `textContent` se mide si
  el lector está al final (distancia menor a ~2rem del fondo). Si lo está,
  se hace scroll al nuevo final; si no, se conserva la posición. Abrir el
  modal sigue scrolleando al final una vez, como hoy.
- **Sin carrusel de peticiones**: si una lectura anterior sigue en vuelo, la
  siguiente la pisa solo cuando responda; no se encolan lecturas. Un fallo de
  una lectura no rompe el ciclo: muestra el aviso y sigue.

El texto sigue llegando por `textContent`. El log lo escribe root en el
servidor y contiene rutas absolutas: no hay motivo para interpretarlo como
markup, y el modal lo ve solo el superusuario.

## 6. Qué no cambia

- `deploy_log()` ni el endpoint `update_log`: misma cola, misma cola de
  truncado, mismo `available: false`.
- La escritura de la petición de despliegue, el `O_EXCL`, los estados de
  `build_state` y la regla de `failed`.
- El ritmo de polling: 2 s en `running`, 60 s en reposo.
- Sin dependencias nuevas, sin bundler, sin SSE.

## 7. Límite de entrega

Todo vive en el repo y viaja en el propio deploy: vista JSON, template y JS
estático. Ningún archivo de sistema, ningún script root. Después del deploy
de v0.7.4 este cambio no exige ningún comando en el server.
