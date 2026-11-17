# 039-version-y-log-vivo — propuesta

> **Estado: aprobada el 2026-11-17.** El usuario pidió el diseño con «si me va
> ese diseño para 039» y lo aclaró con «la idea es ver el log en vivo en el
> modal». La premisa sigue siendo la misma que 037/038: el contenedor se entrega
> **sin SSH**, así que el panel tiene que ser la única ventana al servidor.

## 1. Motivación

El menú de actualizaciones muestra SHA (`9a69fcb → dd1a59c`) y el botón dice
«Actualizar ahora». Nadie que opera el panel piensa en SHAs: piensa en
versiones. El repo ya tiene tags `v0.7.3` apuntando a cada release, y el panel
los ignora.

El log del despliegue, además, solo se lee al abrir el modal. Durante un
deploy de cinco minutos el operador abre el modal, ve las primeras líneas y
tiene que apretar «Actualizar» a mano para saber por dónde va: el botón es
falso vivo.

## 2. Solución

**Chip de versión.** `git ls-remote` se amplía para traer también
`refs/tags/*` (con su peeled `^{}`). La regla de versión es un tag que
apunte **exacto** al commit, prefiriendo `v*` y estable antes que prerelease;
sin tag exacto no hay versión y el panel cae al rango de SHA de siempre. El
menú muestra el chip con la versión instalada, el botón pasa a «Actualizar a
vX.Y.Z» y el detalle a «Instala vX.Y.Z (sha)…».

**Log en vivo.** Con el modal abierto y el despliegue en curso, el JS relee el
log en cada ciclo de polling de estado (2 s). Al terminar, una última lectura.
El autoscroll solo arrastra si el lector está cerca del final: quien está
leyendo una parte antigua del log no pierde su lugar. Todo con `textContent`.
Sin SSE ni WebSocket: el polling que ya existe alcanza.

## 3. Criterios de aceptación

- El chip muestra la versión del commit desplegado cuando un tag (prefiriendo
  `v*`, estable antes que prerelease) apunta exacto a él.
- Sin tag exacto el chip muestra el SHA corto, como hoy, y el botón y el
  detalle siguen con el rango de SHA: nada se inventa.
- El botón dice «Actualizar a vX.Y.Z» y el detalle «Instala vX.Y.Z (sha)…»
  solo cuando hay versión; sin ella, el texto actual sin cambios.
- Con el modal abierto y `running`, el log se relée en cada ciclo de polling;
  hay una última lectura al pasar a `ok`/`failed`; el autoscroll solo se
  aplica si el lector está cerca del final.
- Todo el texto llega por `textContent`, nunca `innerHTML`.
- `python manage.py test apps.dashboard` en verde, ruff y djlint limpios.
- `deploy/README-deploy.md` documenta el chip y el log en vivo.

## 4. Límite de entrega

Ningún archivo de este cambio vive fuera del repo: el chip, el botón y el log
son panel + JS estático + la vista JSON que ya existe. Después del deploy de
v0.7.4 **no hace falta ningún comando en el server** para este cambio.
