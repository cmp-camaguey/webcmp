# 041-respaldo-import-export — requisitos

## S1 — Descargar respaldo
- Superusuario solicita descarga de un nombre presente en manifiesto; confirmación `DESCARGAR`.
- Se crea `download-request` con O_EXCL; conflicto si ya hay pendiente.
- Ejecutor copia dump a staging con token aleatorio, TTL; escribe `download-status.json`.
- Vista `/dashboard/database/download/<token>/` sirve attachment autenticado, audita, invalida/elimina staging.
- Token inválido/expirado/consumido devuelve 404. Web nunca lee `DB_BACKUP_DIR`.

## S2 — Subir y restaurar
- Superusuario sube `.dump` con confirmación `RESTAURAR`; límite de tamaño.
- Web guarda en staging upload, nunca en `DB_BACKUP_DIR`; escribe `restore-request` con `source=upload`.
- Ejecutor valida con `pg_restore --list`, mueve a `DB_BACKUP_DIR` como `*-uploaded.dump`, ejecuta restore 040.
- Validación falla -> failed, no restaura, borra staged.

## S3 — Auditoría y limpieza
- Log de acciones download/upload/restore.
- Ejecutor limpia staging vencido.

## S4 — Pruebas
- Django: permisos, validación, tokens, upload size/ext, serving.
- Shell: validación nombre/token, pg_restore --list gate, staging cleanup, units.
