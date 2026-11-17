# Modo `--backup` de deploy.sh (TEST-BLOCK `backup-mode`).
#
# Por que existe esta prueba, con nombre y apellido: la primera version del modo
# estaba despues del pedido de commit-sha y moria en el preflight, y las 232
# pruebas de entonces no lo vieron porque todas miraban el texto de `--help` o
# hacian `assert_contains` sobre el fuente. Un `assert_contains` prueba que una
# cadena esta escrita, no que el camino se ejecute.
#
# Se corre el bloque de verdad, con `db_dump` y `prune_db_backups` reemplazados:
# el contrato es que falle cerrado, que no rote si el dump fallo, y que rote
# despues cuando salio bien.
#
# Se ejecuta con `source` desde run.sh; no se corre solo.

BACKUP_MODE_SH=$REPO_ROOT/deploy/deploy.sh
backup_mode_block=$(require_block backup-mode "$BACKUP_MODE_SH")

backup_mode_tmp=$(mktemp -d)
backup_dumps=$backup_mode_tmp/dumps
mkdir -p "$backup_dumps"

# --- Sin pg_dump: falla cerrado, antes de crear el archivo ----------------
#
# Un archivo vacio con nombre de dump es peor que ninguno: parece un respaldo.

(
    MODE=backup
    DB_BACKUP_DIR=$backup_dumps
    PATH=/nonexistent
    log() { :; }
    die() { printf 'DIE:%s\n' "$*"; exit 1; }
    eval "$backup_mode_block"
) >"$backup_mode_tmp/no-pg-dump.log" 2>&1
no_pg_dump_rc=$?

assert_eq 'backup: sin pg_dump sale 1' 1 "$no_pg_dump_rc"
assert_contains 'backup: sin pg_dump lo explica' 'No hay pg_dump' \
    "$(cat "$backup_mode_tmp/no-pg-dump.log")"
assert_eq 'backup: sin pg_dump no deja archivos' '0' \
    "$(find "$backup_dumps" -type f | wc -l | tr -d ' ')"

# --- El dump falla: borra el parcial y no rota ----------------------------

(
    MODE=backup
    DB_BACKUP_DIR=$backup_dumps
    log() { :; }
    die() { printf 'DIE:%s\n' "$*"; exit 1; }
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

# --- Camino feliz: volcar, recien despues rotar ---------------------------

(
    MODE=backup
    DB_BACKUP_DIR=$backup_dumps
    log() { :; }
    die() { printf 'DIE:%s\n' "$*"; exit 1; }
    db_dump() { printf 'DUMP'; printf 'contenido' > "$1"; }
    prune_db_backups() { printf 'PRUNE'; }
    eval "$backup_mode_block"
) >"$backup_mode_tmp/ok.log" 2>&1
ok_rc=$?

assert_eq 'backup: el camino feliz sale 0' 0 "$ok_rc"
assert_eq 'backup: rota despues de volcar' 'DUMPPRUNE' \
    "$(cat "$backup_mode_tmp/ok.log")"
# El nombre lleva el sufijo `-scheduled`, que es lo que distingue un respaldo
# programado del que hace el deploy antes de migrar.
assert_eq 'backup: el archivo se llama como programado' '1' \
    "$(find "$backup_dumps" -type f -name '*-scheduled.dump' | wc -l | tr -d ' ')"
assert_eq 'backup: el respaldo queda solo para root' '600' \
    "$(stat -c '%a' "$backup_dumps/"*-scheduled.dump)"

rm -rf "$backup_mode_tmp"
