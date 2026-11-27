# 041-respaldo-import-export — diseño

## Archivos

| Archivo | Dueño | Modo |
| --- | --- | --- |
| `DB_BACKUP_DIR` | root:root | 0700, dumps 0600 (sin cambio) |
| `DB_DOWNLOAD_STAGING_DIR` `/var/lib/webcmp/downloads` | root:webcmp | 0750, archivos 0640 |
| `DB_UPLOAD_STAGING_DIR` `/var/lib/webcmp/uploads` | root:webcmp | 0750, archivos 0640 |
| `download-request` | webcmp | 0644 JSON |
| `download-status.json` | root | 0644 JSON |
| `restore-request` | webcmp | 0644 JSON (extiende 040 con `source=upload`) |

## Descarga

1. POST `database/download/request/` `{filename, confirm:"DESCARGAR"}`. Valida nombre en manifiesto.
2. Escribe `download-request` (O_EXCL). El ejecutor (`--download-request`) valida nombre real en DB_BACKUP_DIR, genera token aleatorio, copia dump a staging con nombre `<token>.dump`, escribe `download-status.json` `{status, token, filename, download_name, expires_at}`.
3. UI hace polling a `database/data/` que incluye `download`. Cuando `ok`, muestra enlace a `database/download/<token>/`.
4. Vista descarga: superusuario, token hex válido, busca archivo en staging, `FileResponse` attachment, registra auditoría, elimina archivo staging tras servir (o marca consumido). Token inválido/expirado/consumido -> 404.
5. Ejecutor limpia staging vencido en cada corrida.

## Subida + restauración

1. POST multipart `database/upload/` con `file` + `confirm=RESTAURAR`. Web valida extensión `.dump`, tamaño <= `DB_UPLOAD_MAX_SIZE`, nombre saneado. Guarda en staging subidas como `<random>.upload.dump` (0640). Escribe `restore-request` con `source:"upload", staged_file:"<random>.upload.dump", original_name:"..."`.
2. Ejecutor `--restore-request`: si `source==upload`, resuelve staged_file dentro de upload staging (realpath, no symlink, regular). Ejecuta `pg_restore --list` para validar formato custom; si falla, estado failed y borra staged. Si ok, mueve a `DB_BACKUP_DIR/webcmp-<ts>-uploaded.dump`, luego ejecuta flujo restore 040 normal. Siempre borra staged upload al final.

## Seguridad

- Nombres validados con mismo regex de 040 + token `[a-f0-9]{64}`.
- Nunca servir desde DB_BACKUP_DIR. Nunca confiar en path del request.
- Auditoría con `log_action` para request/download/upload/restore.
- `Content-Disposition` attachment, `nosniff`.
- Límite tamaño upload (default 512 MiB, configurable).
- `pg_restore --list` antes de mover/restore upload.
