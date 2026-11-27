# Archivos de estado y manifiesto del panel de respaldo (change 040).
#
# Estos tres bloques son el contrato entre el ejecutor root y el proceso web: el
# ejecutor escribe JSON en /var/lib/webcmp y el panel lo lee. Un JSON mal armado
# no falla donde se escribe, falla en la pagina, y el operador ve "sin datos"
# sin ninguna pista.
#
# Se prueba lo que se puede probar sin root: la forma del JSON, el orden del
# manifiesto, la validacion del nombre a restaurar y el modo `--backup-list`.
# La lectura del dump y el `pg_restore` se prueban en el servidor.
#
# Se ejecuta con `source` desde run.sh; no se corre solo.

DB_SH=$REPO_ROOT/deploy/deploy.sh
db_json_block=$(require_block db-json "$DB_SH")
db_status_block=$(require_block db-status "$DB_SH")
db_manifest_block=$(require_block db-manifest "$DB_SH")
db_request_block=$(require_block db-request-reader "$DB_SH")
restore_validation_block=$(require_block restore-validation "$DB_SH")
backup_list_block=$(require_block backup-list-mode "$DB_SH")

db_tmp=$(mktemp -d)
mkdir -p "$db_tmp/db" "$db_tmp/state"

# --- json_escape: comillas y barras ---------------------------------------

json_escaped=$(
    eval "$db_json_block"
    json_escape 'a"b\c'
)
assert_eq 'json: escapa comilla y barra invertida' 'a\"b\\c' "$json_escaped"

# --- write_db_status ------------------------------------------------------

status_file=$db_tmp/state/backup-status.json

(
    eval "$db_json_block"
    eval "$db_status_block"
    DB_BACKUP_STATUS_FILE=$status_file
    DB_OP_STARTED_AT='2026-11-27T08:00:00-05:00'
    REQUESTED_BY='operador'
    write_db_status backup running 'Respaldo en curso.'
) || true
status_running=$(cat "$status_file" 2>/dev/null || true)

assert_contains 'status: el running no tiene finished_at' '"finished_at": null' "$status_running"
assert_contains 'status: guarda el instante de arranque' \
    '"started_at": "2026-11-27T08:00:00-05:00"' "$status_running"
assert_contains 'status: guarda quien lo pidio' '"requested_by": "operador"' "$status_running"
assert_eq 'status: queda legible para el proceso web' '644' \
    "$(stat -c '%a' "$status_file" 2>/dev/null || echo '?')"

(
    eval "$db_json_block"
    eval "$db_status_block"
    DB_BACKUP_STATUS_FILE=$status_file
    DB_OP_STARTED_AT='2026-11-27T08:00:00-05:00'
    REQUESTED_BY='operador'
    write_db_status restore failed 'Fallo.' 'webcmp-x.dump' 'webcmp-y.dump'
) || true
status_failed=$(cat "$status_file" 2>/dev/null || true)

assert_contains 'status: el fallo lleva finished_at' '"finished_at": "' "$status_failed"
assert_contains 'status: el fallo nombra el dump pedido' '"file": "webcmp-x.dump"' "$status_failed"
# El dump de seguridad es lo que permite reintentar desde el panel sin SSH.
assert_contains 'status: el fallo nombra el respaldo de seguridad' \
    '"safety_file": "webcmp-y.dump"' "$status_failed"
assert_contains 'status: el fallo conserva el estado' '"status": "failed"' "$status_failed"

# --- read_requested_by / read_restore_file --------------------------------

printf '{"file": "a.dump", "requested_by": "operador"}' > "$db_tmp/state/restore-request"
request_values=$(
    eval "$db_request_block"
    eval "$restore_validation_block"
    printf '%s|%s' \
        "$(read_requested_by "$db_tmp/state/restore-request")" \
        "$(read_restore_file "$db_tmp/state/restore-request")"
)
assert_eq 'request: lee el autor y el archivo' 'operador|a.dump' "$request_values"

# --- write_db_manifest: orden, tamano y origen ----------------------------

manifest_file=$db_tmp/state/backup-manifest.json
printf 'viejo' > "$db_tmp/db/webcmp-20260101T000000Z-scheduled.dump"
printf 'medio' > "$db_tmp/db/webcmp-20260102T000000Z-manual.dump"
printf 'nuevo!!' > "$db_tmp/db/webcmp-20260103T000000Z-pre-restore.dump"
touch -d '2026-01-01 00:00:00' "$db_tmp/db/webcmp-20260101T000000Z-scheduled.dump"
touch -d '2026-01-02 00:00:00' "$db_tmp/db/webcmp-20260102T000000Z-manual.dump"
touch -d '2026-01-03 00:00:00' "$db_tmp/db/webcmp-20260103T000000Z-pre-restore.dump"

(
    eval "$db_json_block"
    eval "$db_manifest_block"
    DB_BACKUP_DIR=$db_tmp/db
    DB_BACKUP_KEEP=7
    DB_BACKUP_MANIFEST_FILE=$manifest_file
    write_db_manifest
) || true
manifest=$(cat "$manifest_file" 2>/dev/null || true)

assert_contains 'manifiesto: declara la retencion' '"keep": 7' "$manifest"
assert_contains 'manifiesto: declara el directorio' "\"dir\": \"$db_tmp/db\"" "$manifest"
# El mas nuevo va primero: es el que el operador busca cuando algo acaba de
# romperse.
assert_eq 'manifiesto: ordena del mas nuevo al mas viejo' \
    'webcmp-20260103T000000Z-pre-restore.dump webcmp-20260102T000000Z-manual.dump webcmp-20260101T000000Z-scheduled.dump' \
    "$(grep -o '"name": "[^"]*"' "$manifest_file" | cut -d'"' -f4 | paste -sd' ' -)"
assert_contains 'manifiesto: marca el origen manual' '"kind": "manual"' "$manifest"
assert_contains 'manifiesto: marca el origen programado' '"kind": "scheduled"' "$manifest"
assert_contains 'manifiesto: marca el respaldo de seguridad' '"kind": "pre-restore"' "$manifest"
assert_contains 'manifiesto: incluye el tamano' '"size": 7' "$manifest"
assert_eq 'manifiesto: queda legible para el proceso web' '644' \
    "$(stat -c '%a' "$manifest_file" 2>/dev/null || echo '?')"

# --- Validacion del nombre a restaurar ------------------------------------

validation_result=$(
    eval "$restore_validation_block"
    for name in webcmp-20261127T031500Z-scheduled.dump a.dump A_b-c.dump; do
        valid_backup_name "$name" && printf 'ok '
    done
    for name in '' '../etc/passwd.dump' '/var/backups/webcmp/db/a.dump' \
        'sub/a.dump' 'a.sql' '-a.dump' 'a b.dump'
    do
        valid_backup_name "$name" || printf 'no '
    done
)
assert_eq 'restore: acepta dumps y rechaza rutas y no-dumps' \
    'ok ok ok no no no no no no no ' "$validation_result"

# `resolve_backup_file` exige dueno root, asi que el camino positivo solo se
# puede ejercitar como root. Los negativos si: traversal, symlink y archivo que
# no existe se rechazan ANTES de mirar el dueno.
resolve_negatives=$(
    eval "$restore_validation_block"
    DB_BACKUP_DIR=$db_tmp/db
    printf 'real' > "$db_tmp/db/real.dump"
    ln -s "$db_tmp/db/real.dump" "$db_tmp/db/link.dump"
    for name in '../real.dump' 'no-existe.dump' 'link.dump'; do
        if resolve_backup_file "$name" >/dev/null 2>&1; then
            printf 'ACEPTO:%s ' "$name"
        else
            printf 'rechazo '
        fi
    done
)
assert_eq 'restore: rechaza traversal, inexistente y symlink' \
    'rechazo rechazo rechazo ' "$resolve_negatives"

if [ "$(id -u)" -eq 0 ]; then
    positive=$(
        eval "$restore_validation_block"
        DB_BACKUP_DIR=$db_tmp/db
        resolve_backup_file real.dump 2>/dev/null || true
    )
    assert_eq 'restore: acepta un dump de root' "$(realpath -e "$db_tmp/db/real.dump")" \
        "$positive"
else
    printf '  omitido  resolve_backup_file positivo: la suite no corre como root\n'
fi

# --- --backup-list: refresca el manifiesto sin respaldar ------------------

(
    eval "$db_json_block"
    eval "$db_manifest_block"
    eval "$backup_list_block"
    MODE=backup-list
    DB_BACKUP_DIR=$db_tmp/db
    DB_BACKUP_KEEP=10
    DB_BACKUP_MANIFEST_FILE=$db_tmp/state/list-manifest.json
    die() { printf 'DIE:%s\n' "$*"; exit 1; }
) >"$db_tmp/list.log" 2>&1
list_rc=$?
assert_eq 'backup-list: sale 0' 0 "$list_rc"
assert_file 'backup-list: escribe el manifiesto' "$db_tmp/state/list-manifest.json"

(
    eval "$db_json_block"
    eval "$db_manifest_block"
    eval "$backup_list_block"
    MODE=backup-list
    DB_BACKUP_DIR=$db_tmp/db
    DB_BACKUP_KEEP=10
    DB_BACKUP_MANIFEST_FILE=$db_tmp/no-existe/state/manifest.json
    die() { printf 'DIE:%s\n' "$*"; exit 1; }
) >"$db_tmp/list-fail.log" 2>&1
assert_eq 'backup-list: sin directorio de estado falla' 1 "$?"

rm -rf "$db_tmp"
