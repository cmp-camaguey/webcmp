# 037-log-del-despliegue — diseño

## 1. Por qué un archivo y no leer el journal desde la web

Leer el journal expondría al proceso web privilegios de `systemd`/`polkit` que no
tiene (corre con shell `/bin/false` y sin sudo, a propósito: ver
`README-deploy.md`, "El botón Actualizar"). Un archivo en el mismo directorio
que `deploy-status.json` reutiliza el andamiaje ya instalado: directorio 2775
setgid, permisos 0644, lectura validada por el panel.

El journal sigue recibiendo exactamente lo mismo. El archivo es para quien no
tiene SSH; el journal, para quien lo tiene (incluye lo anterior a este cambio).

## 2. Quién escribe y quién rota

El ejecutor (`autodeploy.sh`, usuario `deploy`) escribe. Nadie rota este archivo
—no hay `logrotate` en el contenedor—, así que lo rota el propio ejecutor antes
de cada corrida: si pasa de `DEPLOY_LOG_MAX_BYTES` (512 KB) conserva la última
mitad. Con el tope a la mitad el archivo nunca pasa de ~1.5x el tope, y no hace
falta un servicio de rotación que instalar.

El recorte es por bytes (`tail -c`) y no por líneas: una línea de `pip install`
puede pesar más que un bloque razonable de renglones.

## 3. Por qué `tee` con `PIPESTATUS`, no `set -e`

La salida del deploy va al journal (stdout de la unidad) y al archivo en la misma
corriente. El código de salida que importa es el del deploy, no el de `tee`:
`deploy_rc=${PIPESTATUS[0]}`. Un `tee` que no puede escribir (disco lleno) no
puede convertir un deploy que salió bien en un fallo, ni tapar el estado del
panel; por eso el bloque va con `set +e` alrededor: con `pipefail` activo, el
mismo `tee` fallido mataría el script ahí.

## 4. Cola, no archivo entero

El panel devuelve los últimos `UPDATE_LOG_MAX_BYTES` (32 KB). La causa del fallo
está al final, y el archivo completo puede pesar megas tras un `pip install`
largo. Si el corte cae a mitad de una línea, se descarta el renglón parcial:
presentar como inicio del log una línea a medias induce a leer un mensaje
incompleto.

## 5. Filtro: no hay, y es deliberado

`deploy-status.json` no reenvía el contenido tal cual (stderr de git con rutas
absolutas). El log sí: lo ve el superusuario que ya dispara los deploys y lee el
estado, que es el único que puede llegar ahí. Filtrarlo dejaría el modal sin la
causa del fallo, que es exactamente lo que existe este cambio.

## 6. Dónde se lee

El JS lo trae en `show.bs.modal`, no en el polling: es un archivo de sistema y
leerlo cada 2 s durante un despliegue sería cargar el panel con una línea de pip
otra vez. `textContent` y no `innerHTML`: el contenido lo escribe root en el
servidor, y aun así no hay motivo para interpretarlo como markup. El `<pre>`
se abre scrolleado hasta el final, donde está el resultado.
