# 037-log-del-despliegue — propuesta

> **Estado: aprobada el 2026-11-17.** El usuario pidió poder ver desde el panel
> el log del deploy, porque al entregar el contenedor al proveedor ya no habrá
> acceso SSH al servidor.

## 1. Motivación

Cuando el botón **Actualizar** falla, el motivo vive en el journal
(`journalctl -u webcmp-autodeploy`): el panel solo puede mostrar un mensaje fijo
y el estado `failed`. Eso fue suficiente hasta hoy, con SSH al servidor. A partir
de la entrega al proveedor, nadie tendrá SSH: el fallo del 2026-11-17 (health
check 503 tras el reintento de v0.7.2) solo se pudo diagnosticar leyendo el
journal a mano.

El journal no es legible desde la web: el proceso corre con `/bin/false` como
shell, sin sudo, y `journalctl` no está a su alcance ni conviene dárselo.

## 2. Solución

- **`deploy/autodeploy.sh`** escribe cada intento a
  `/var/lib/webcmp/deploy.log` (0644, mismo directorio que el estado) además del
  journal: es la misma corriente, `tee -a` la divide. El propio ejecutor rota el
  archivo antes de cada corrida (tope 512 KB, conserva la mitad). Un log
  inescribible no puede tumbar un deploy que salió bien.
- **`UpdateLogView`** (superusuario) devuelve la cola del archivo (32 KB) como
  JSON, marcando si se truncó. El contenido NO se filtra: son rutas absolutas del
  servidor, y por eso el público se limita al superusuario que ya dispara deploys.
- **El desplegable** gana un botón siempre visible, **"Ver log del despliegue"**,
  que abre un modal con el log cargado al abrirse (no en el polling: es un
  archivo de sistema). El mensaje de fallo apunta al modal en vez de decir
  "revisa el log del servidor", que sin SSH no es ninguna indicación.

## 3. Criterios de aceptación

- La salida del deploy (stdout y stderr) llega al archivo, no solo al journal.
- El archivo queda 0644 y el panel lo lee; sin archivo el modal lo dice, sin 500.
- El recorte conserva la cola y el archivo no crece sin techo.
- `make test-deploy` y `python manage.py test apps.dashboard` en verde.
- `deploy/README-deploy.md` documenta el archivo, sus topes y el botón.
