# 041-respaldo-import-export — tareas

- [x] 1. Settings: `DB_DOWNLOAD_STAGING_DIR`, `DB_UPLOAD_STAGING_DIR`, `DB_DOWNLOAD_TTL_SECONDS`, `DB_UPLOAD_MAX_SIZE`.
- [x] 2. Servicio: tokens, download-request/status, staging cleanup metadata, upload validation, audit helpers.
- [x] 3. Vistas/URLs: download request, download serve, upload; permisos, CSRF, 403.
- [x] 4. Template/JS: botones Descargar/Subir, modal confirmación, polling download status, formulario upload.
- [x] 5. `deploy.sh`: `--download-request`, cleanup staging, upload-restore validation `pg_restore --list`, source=upload.
- [x] 6. Systemd/instaladores/manifiesto: `webcmp-download.path/service`, staging dirs.
- [x] 7. Tests Django + tests shell.
- [x] 8. Docs, ruff/djlint/check, verificación final y commit.
