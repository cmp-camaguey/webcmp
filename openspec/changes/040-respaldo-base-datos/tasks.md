# 040-respaldo-base-datos — tareas

- [x] 1. Tests RED Django: `apps/dashboard/services/backup.py` (manifiesto,
      estado, validación de nombre, peticiones) y vistas. (S1–S4)
      Evidencia: 30 pruebas, `apps/dashboard/tests/test_database_backup.py`.
- [x] 2. `config/settings/base.py`: rutas y retención. (S2–S6)
- [x] 3. `apps/dashboard/services/backup.py`: helpers con lectura tolerante y
      `stale`. (S2–S4)
- [x] 4. `apps/dashboard/views/dashboard/database.py` + `urls.py`: página,
      JSON, peticiones y 403. (S1–S4)
- [x] 5. `database.html` + `dashboard-database.js` + menú **Sistema**. (S1–S4)
- [x] 6. `deploy/deploy.sh`: estado, manifiesto, `--backup-manual`,
      `--backup-list`, `--restore`, `--restore-request`. (S5–S6)
- [x] 7. Unidades systemd nuevas + `install.sh` + `install-backup-units.sh` +
      `root-bundle.manifest`. (S7)
- [x] 8. Tests shell RED→GREEN: validación, manifiesto, estado, instalador.
      (S5–S7)
      Evidencia: `test_deploy_sh_backup_panel.sh`,
      `test_deploy_sh_restore_mode.sh`, `test_deploy_sh_backup_mode.sh`,
      `test_install_backup_units.sh`.
- [x] 9. `deploy/README-deploy.md` y `deploy/deploy.env.example`. (S8)
- [x] 10. Suite completa, ruff, djlint y `make test-deploy`. (todas)
      Evidencia: `apps.dashboard` 214 pruebas OK, ruff y djlint limpios,
      `deploy/tests/run.sh` sin fallas.
