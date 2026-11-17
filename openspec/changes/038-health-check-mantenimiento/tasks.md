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
- [ ] 6. PR a `dev`. (S6)
- [ ] 7. Después de que el commit esté desplegado, reinstalar la copia root de
      `deploy.sh` en el servidor —único paso manual, y previo a la entrega del
      contenedor—. (S6)
