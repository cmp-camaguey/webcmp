# 041-respaldo-import-export — propuesta

> **Estado: aprobado por el usuario el 2026-11-27.** Sin SSH en producción, el
> operador necesita sacar respaldos a un USB desde su laptop y poder cargar un
> dump externo para restaurarlo en un deploy nuevo.

## 1. Motivación

El change 040 permite crear, listar y restaurar respaldos que ya existen en el
servidor. Pero el contenedor de producción se entrega sin SSH: si el servidor se
pierde, no hay forma de llevarse un `.dump` a un USB ni de volver a cargar uno
desde fuera.

## 2. Solución

Extender el módulo «Respaldo de BD» con dos acciones controladas:

1. **Descargar** un respaldo existente. El proceso web no lee el dump original.
   Escribe una petición; el ejecutor root copia el dump a un staging temporal con
   token aleatorio, TTL corto y permisos `0640 root:webcmp`. La vista Django
   autentica al superusuario, verifica el token y sirve el archivo; lo elimina al
   completar o al vencer.
2. **Subir y restaurar** un dump externo. El web recibe el archivo por upload
   autenticado, lo guarda en staging de subidas (fuera de `DB_BACKUP_DIR`), y el
   ejecutor valida que sea un `pg_dump --format=custom` real (`pg_restore --list`)
   antes de moverlo a `DB_BACKUP_DIR` como `*-uploaded.dump` y restaurarlo con el
   mismo flujo seguro del 040 (respaldo de seguridad, stop/start, estado).

Ambas acciones quedan auditadas. Los dumps originales siguen `0600 root:root` en
`0700`.

## 3. Criterios de aceptación

- Descargar exige superusuario, respaldo en manifiesto, confirmación, y genera
  token de un solo uso con TTL.
- El ejecutor prepara el staging; el web nunca lee `DB_BACKUP_DIR`.
- La descarga se sirve autenticada, con `Content-Disposition: attachment`, y el
  staging se limpia.
- Subir exige superusuario, extensión `.dump`, límite de tamaño, confirmación
  `RESTAURAR`; el archivo queda en staging de subidas, no en `DB_BACKUP_DIR`.
- El ejecutor valida el dump subido con `pg_restore --list`; si no es válido,
  falla cerrado y no restaura.
- El restore de un dump subido usa el mismo flujo 040 (safety dump, stop/start
  siempre, estado, manifiesto).
- Auditoría: solicitud de descarga, descarga completada/expirada, subida,
  validación fallida, restore iniciado/finalizado.
- Tests Django y deploy/shell verdes.

## 4. Fuera de alcance

- Push automático a S3/SFTP (puede ser 042).
- Cifrado age/gpg del artefacto (opcional futuro).
- Restaurar subiendo SQL plano; solo `pg_dump --format=custom`.
