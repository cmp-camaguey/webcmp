# 038-health-check-mantenimiento — tareas

- [x] 1. `deploy/deploy.sh`: `site_in_maintenance()`, `health_probe_login()` y
      `health_verdict()` en el bloque `TEST-BLOCK: health-verdict`; el `case`
      inline del paso 9 pasa a una llamada a `health_verdict "$code"`. (S1, S2,
      S3)
- [x] 2. `deploy/tests/test_deploy_sh_health.sh`: los cuatro caminos del 503,
      2xx/3xx/000/404 sin cambios, la URL y el transporte del probe de `/login/`,
      y el filtrado de la salida de `manage.py`. Registrado en
      `deploy/tests/test_shell_scripts.sh`. (S4)
- [x] 3. `deploy/README-deploy.md`: sección «Health check» con la tabla de
      resultados. (S5)
- [x] 4. Documentación OpenSpec del cambio. (todas)
- [x] 5. `make test-deploy` en verde (274 ok, 0 fallos). (S4)
- [x] 6. PR a `dev`: #246, squash `708be70`. (S6)
- [ ] 7. Antes de la entrega del contenedor, reinstalar en el server las dos
      copias root desde el checkout ya desplegado —único paso manual; después
      de él ningún camino de 037 ni de 038 exige un comando en el server:
      `sudo install -o root -g root -m 0755 /srv/webcmp/deploy/deploy.sh /usr/local/sbin/webcmp-deploy` (S6)
      `sudo install -o root -g root -m 0755 /srv/webcmp/deploy/autodeploy.sh /usr/local/sbin/webcmp-autodeploy` (037: sin esto `/var/lib/webcmp/deploy.log` no se escribe y el modal del panel sale vacío)
- [x] 8. Quitar el `2>/dev/null` de `site_in_maintenance` (hallazgo del
      verificador independiente): `run_in_unit` fusiona el stderr de la unidad
      transitoria en el stdout, así que el redirect no ocultaba el ruido que
      quería ocultar y sí tiraba el motivo de `systemd-run` fuera del journal.
      El filtro real sigue siendo `grep -qx True`. (S2)
