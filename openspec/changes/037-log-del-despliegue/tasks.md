# 037-log-del-despliegue — tareas

- [x] 1. `deploy/autodeploy.sh`: `DEPLOY_LOG`, `DEPLOY_LOG_MAX_BYTES`,
      `prepare_log()` y `log()` que escribe a archivo + journal; el deploy pasa
      por `tee -a` con `deploy_rc=${PIPESTATUS[0]}`. (S1, S2)
- [x] 2. `config/settings/base.py`: `UPDATE_LOG_FILE` y `UPDATE_LOG_MAX_BYTES`. (S3)
- [x] 3. `deploy_log()` y `UpdateLogView` en `apps/dashboard/views/dashboard/update.py`,
      ruta `update/log/` en `apps/dashboard/urls.py`. (S3, S4)
- [x] 4. Botón "Ver log del despliegue" y modal en
      `templates/includes/dashboard/update_navbar.html`; `loadLog`/`paintLog` en
      `static/dist/js/dashboard-update.js`; el mensaje de fallo apunta al modal. (S5)
- [x] 5. `deploy/tests/test_autodeploy_log.sh`: salida al archivo, 0644, recorte,
      log inescribible, código de salida del deploy. Registrado en
      `test_shell_scripts.sh`. (S6)
- [x] 6. Tests Django del endpoint en `apps/dashboard/tests/test_update.py`:
      403 sin superusuario, sin archivo, cola truncada, OSError, mensaje de fallo. (S6)
- [x] 7. `deploy/README-deploy.md`: archivo, topes, botón y fila de permisos. (S7)
- [x] 8. Documentación OpenSpec del cambio. (todas)
- [x] 9. `make test-deploy` (269 ok, 0 fallos) y `python manage.py test
      apps.dashboard` (134 OK) en verde; ruff y djlint limpios; PR a `dev`. (S6)
