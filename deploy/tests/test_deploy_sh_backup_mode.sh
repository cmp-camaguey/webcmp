# Modo `--backup` de deploy.sh (TEST-BLOCK `backup-mode`).
#
# Por que existe esta prueba, con nombre y apellido: la primera version del modo
# estaba despues del pedido de commit-sha y moria en el preflight, y las 232
# pruebas de entonces no lo vieron porque todas miraban el texto de `--help` o
# hacian `assert_contains` sobre el fuente. Un `assert_contains` prueba que una
# cadena esta escrita, no que el camino se ejecute.
#
# Se corre el bloque de verdad, con `db_dump`, `prune_db_backups` y las
# funciones de estado/manifiesto reemplazadas: el contrato es que falle cerrado,
# que no rote si el dump fallo, que rote despues cuando salio bien, y que el
# respaldo manual se distinga del programado.
#
# Se ejecuta con `source` desde run.sh; no se corre solo.

BACKUP_MODE_SH=$REPO_ROOT/deploy/deploy.sh
backup_mode_block=$(require_block backup-mode "$BACKUP_MODE_SH")

backup_mode_tmp=$(mktemp -d)
backup_dumps=$backup_mode_tmp/dumps
mkdir -p "$backup_dumps"

# Los stubs comunes a todos los casos. `write_db_status`/`write_db_manifest`
# dejan rastro en el log para poder afirmar el ORDEN: estado antes de respaldar,
# manifiesto despues de rotar.
backup_mode_env() {
    MODE=backup
    DB_BACKUP_DIR=$backup_dumps
    DB_BACKUP_REQUEST_FILE=$backup_mode_tmp/backup-request
    DB_BACKUP_STATUS_FILE=$backup_mode_tmp/status.json
    DB_BACKUP_MANIFEST_FILE=$backup_mode_tmp/manifest.json
    log() { :; }
    die() { printf 'DIE:%s\n' "$*"; exit 1; }
    write_db_status() { printf 'STATUS:%s:%s\n' "$1" "$2"; }
    write_db_manifest() { printf 'MANIFEST\n'; }
    read_requested_by() { printf 'operador'; }
}

# --- Sin pg_dump: falla cerrado, antes de crear el archivo ----------------
#
# Un archivo vacio con nombre de dump es peor que ninguno: parece un respaldo.
# `command` se reemplaza en vez de vaciar PATH para no perder `date`, que el
# bloque usa para el instante de arranque.

(
    backup_mode_env
    BACKUP_KIND=scheduled
    command() { return 1; }
    eval "$backup_mode_block"
) >"$backup_mode_tmp/no-pg-dump.log" 2>&1
no_pg_dump_rc=$?
no_pg_dump_log=$(cat "$backup_mode_tmp/no-pg-dump.log")

assert_eq 'backup: sin pg_dump sale 1' 1 "$no_pg_dump_rc"
assert_contains 'backup: sin pg_dump lo explica' 'No hay pg_dump' "$no_pg_dump_log"
assert_eq 'backup: sin pg_dump no deja archivos' '0' \
    "$(find "$backup_dumps" -type f | wc -l | tr -d ' ')"
# El estado tiene que quedar en `failed`: si quedara en `running`, el panel
# bloquearia el boton para siempre y el operador no tendria como reintentar.
assert_contains 'backup: sin pg_dump deja estado failed' 'STATUS:backup:failed' \
    "$no_pg_dump_log"
assert_contains 'backup: sin pg_dump refresca el manifiesto' 'MANIFEST' \
    "$no_pg_dump_log"

# --- El dump falla: borra el parcial y no rota ----------------------------

(
    backup_mode_env
    BACKUP_KIND=scheduled
    db_dump() { printf 'parcial' > "$1"; return 1; }
    prune_db_backups() { printf 'PRUNE'; }
    eval "$backup_mode_block"
) >"$backup_mode_tmp/dump-falla.log" 2>&1
dump_falla_rc=$?

assert_eq 'backup: un dump fallido sale 1' 1 "$dump_falla_rc"
assert_eq 'backup: el dump parcial se borra' '0' \
    "$(find "$backup_dumps" -type f | wc -l | tr -d ' ')"
assert_not_contains 'backup: no rota si el dump fallo' 'PRUNE' \
    "$(cat "$backup_mode_tmp/dump-falla.log")"
assert_contains 'backup: un dump fallido deja estado failed' \
    'STATUS:backup:failed' "$(cat "$backup_mode_tmp/dump-falla.log")"

# --- Camino feliz: volcar, recien despues rotar ---------------------------

(
    backup_mode_env
    BACKUP_KIND=scheduled
    db_dump() { printf 'DUMP'; printf 'contenido' > "$1"; }
    prune_db_backups() { printf 'PRUNE'; }
    eval "$backup_mode_block"
) >"$backup_mode_tmp/ok.log" 2>&1
ok_rc=$?
ok_log=$(cat "$backup_mode_tmp/ok.log")

assert_eq 'backup: el camino feliz sale 0' 0 "$ok_rc"
assert_eq 'backup: rota despues de volcar' 'DUMPPRUNE' "$ok_log"
# El nombre lleva el sufijo `-scheduled`, que es lo que distingue un respaldo
# programado del que hace el deploy antes de migrar.
assert_eq 'backup: el archivo se llama como programado' '1' \
    "$(find "$backup_dumps" -type f -name '*-scheduled.dump' | wc -l | tr -d ' ')"
assert_eq 'backup: el respaldo queda solo para root' '600' \
    "$(stat -c '%a' "$backup_dumps/"*-scheduled.dump)"
assert_contains 'backup: deja estado running al empezar' 'STATUS:backup:running' "$ok_log"
assert_contains 'backup: termina en estado ok' 'STATUS:backup:ok' "$ok_log"
# El manifiesto va DESPUES de rotar: si fuera antes, el panel listaria un dump
# que la rotacion acaba de borrar y el boton de restaurar fallaria.
assert_eq 'backup: el manifiesto se escribe despues de rotar' 'MANIFEST' \
    "$(printf '%s\n' "$ok_log" | tail -n 2 | head -n 1)"

# --- Respaldo manual: consume la peticion y usa otro sufijo ---------------

printf '{"requested_by": "operador"}' > "$backup_mode_tmp/backup-request"
(
    backup_mode_env
    BACKUP_KIND=manual
    db_dump() { printf 'contenido' > "$1"; }
    prune_db_backups() { :; }
    eval "$backup_mode_block"
) >"$backup_mode_tmp/manual.log" 2>&1
manual_rc=$?
manual_log=$(cat "$backup_mode_tmp/manual.log")

assert_eq 'backup manual: sale 0' 0 "$manual_rc"
assert_eq 'backup manual: el archivo se llama como manual' '1' \
    "$(find "$backup_dumps" -type f -name '*-manual.dump' | wc -l | tr -d ' ')"
# La peticion se borra al empezar: mientras el archivo exista, el panel la
# reporta como "nadie la recogio" aunque el respaldo ya este corriendo.
assert_no_file 'backup manual: consume la peticion' "$backup_mode_tmp/backup-request"
assert_contains 'backup manual: reporta el origen' 'Respaldo manual' "$manual_log"

rm -rf "$backup_mode_tmp"
