# Modo `--restore` / `--restore-request` de deploy.sh (TEST-BLOCK `restore-mode`).
#
# Restaurar es la operacion destructiva del modulo: borra y recrea los objetos de
# la base. Lo que se prueba aca es el ORDEN y las garantias que lo hacen
# recuperable, con `db_dump`, `db_restore` y `systemctl` reemplazados:
#
#   1. un nombre invalido no llega a `pg_restore`;
#   2. si falla el respaldo de seguridad, la base no se toca;
#   3. los servicios se levantan SIEMPRE, incluso si el restore falla;
#   4. el estado final dice que paso y nombra el respaldo de seguridad.
#
# La validacion del nombre en si se prueba en test_deploy_sh_backup_panel.sh.
#
# Se ejecuta con `source` desde run.sh; no se corre solo.

RESTORE_MODE_SH=$REPO_ROOT/deploy/deploy.sh
restore_mode_block=$(require_block restore-mode "$RESTORE_MODE_SH")

restore_tmp=$(mktemp -d)
mkdir -p "$restore_tmp/db" "$restore_tmp/state" "$restore_tmp/bin"

cat > "$restore_tmp/bin/systemctl" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
exit 0
STUB
chmod +x "$restore_tmp/bin/systemctl"

restore_env() {
    DB_BACKUP_DIR=$restore_tmp/db
    DB_BACKUP_STATUS_FILE=$restore_tmp/state/status.json
    DB_BACKUP_MANIFEST_FILE=$restore_tmp/state/manifest.json
    DB_RESTORE_REQUEST_FILE=$restore_tmp/state/restore-request
    DB_BACKUP_KEEP=10
    GUNICORN_UNIT=webcmp
    HUEY_UNIT=webcmp-huey
    SYSTEMCTL=$restore_tmp/bin/systemctl
    STUB_LOG=$restore_tmp/systemctl.log
    export STUB_LOG
    log() { printf 'LOG:%s\n' "$*"; }
    warn() { printf 'WARN:%s\n' "$*"; }
    die() { printf 'DIE:%s\n' "$*"; exit 1; }
    write_db_status() { printf 'STATUS:%s:%s:file=%s:safety=%s\n' "$1" "$2" "$4" "$5"; }
    write_db_manifest() { printf 'MANIFEST\n'; }
    read_requested_by() { printf 'operador'; }
    read_restore_file() { printf '%s' "$RESTORE_NAME_FROM_REQUEST"; }
}

# --- Nombre invalido: no se toca la base ----------------------------------

: > "$restore_tmp/systemctl.log"
(
    restore_env
    MODE=restore-request
    RESTORE_NAME_FROM_REQUEST='../evil.dump'
    printf '{}' > "$DB_RESTORE_REQUEST_FILE"
    resolve_backup_file() { return 1; }
    db_dump() { printf 'NO-DEBE-CORRER'; return 0; }
    db_restore() { printf 'NO-DEBE-CORRER'; return 0; }
    eval "$restore_mode_block"
) >"$restore_tmp/invalid.log" 2>&1
invalid_rc=$?
invalid_log=$(cat "$restore_tmp/invalid.log")

assert_eq 'restore: un nombre invalido sale 1' 1 "$invalid_rc"
assert_not_contains 'restore: un nombre invalido no respalda' 'NO-DEBE-CORRER' "$invalid_log"
assert_not_contains 'restore: un nombre invalido no para servicios' 'stop' \
    "$(cat "$restore_tmp/systemctl.log")"
assert_contains 'restore: un nombre invalido deja estado failed' 'STATUS:restore:failed' \
    "$invalid_log"
# La peticion se borra aunque falle: si quedara, el `.path` la volveria a
# disparar y el operador veria un bucle de restauraciones fallidas.
assert_no_file 'restore: consume la peticion aunque falle' \
    "$restore_tmp/state/restore-request"

# --- El respaldo de seguridad falla: no se para nada ----------------------

: > "$restore_tmp/systemctl.log"
(
    restore_env
    MODE=restore
    RESTORE_FILE='bueno.dump'
    resolve_backup_file() { printf '%s\n' "$DB_BACKUP_DIR/$RESTORE_FILE"; }
    db_dump() { printf 'SAFETY-FALLA'; return 1; }
    db_restore() { printf 'NO-DEBE-CORRER'; return 0; }
    eval "$restore_mode_block"
) >"$restore_tmp/safety.log" 2>&1
safety_rc=$?
safety_log=$(cat "$restore_tmp/safety.log")

assert_eq 'restore: si falla el respaldo de seguridad sale 1' 1 "$safety_rc"
assert_contains 'restore: intenta el respaldo de seguridad' 'SAFETY-FALLA' "$safety_log"
assert_not_contains 'restore: sin respaldo de seguridad no restaura' 'NO-DEBE-CORRER' \
    "$safety_log"
assert_not_contains 'restore: sin respaldo de seguridad no para servicios' 'stop' \
    "$(cat "$restore_tmp/systemctl.log")"
assert_contains 'restore: lo deja escrito en el estado' \
    'No se pudo tomar el respaldo de seguridad' "$safety_log"

# --- Camino feliz: seguridad, parar, restaurar, levantar ------------------

: > "$restore_tmp/systemctl.log"
(
    restore_env
    MODE=restore
    RESTORE_FILE='bueno.dump'
    resolve_backup_file() { printf '%s\n' "$DB_BACKUP_DIR/$RESTORE_FILE"; }
    db_dump() { printf 'SAFETY:%s\n' "$1"; printf 'x' > "$1"; }
    db_restore() { printf 'RESTORE:%s\n' "$(basename "$1")"; return 0; }
    eval "$restore_mode_block"
) >"$restore_tmp/ok.log" 2>&1
ok_rc=$?
ok_log=$(cat "$restore_tmp/ok.log")

assert_eq 'restore: el camino feliz sale 0' 0 "$ok_rc"
assert_contains 'restore: toma el respaldo de seguridad antes' 'SAFETY:' "$ok_log"
assert_contains 'restore: restaura el dump pedido' 'RESTORE:bueno.dump' "$ok_log"
assert_contains 'restore: para gunicorn y huey' 'stop webcmp webcmp-huey' \
    "$(cat "$restore_tmp/systemctl.log")"
assert_contains 'restore: vuelve a levantar los servicios' 'start webcmp webcmp-huey' \
    "$(cat "$restore_tmp/systemctl.log")"
assert_contains 'restore: termina en ok' 'STATUS:restore:ok' "$ok_log"
assert_contains 'restore: el estado nombra el respaldo de seguridad' 'safety=webcmp-' \
    "$ok_log"
# El orden importa: parar los servicios antes de que el dump de seguridad este
# completo dejaria el sitio caido sin vuelta atras si ese dump falla.
safety_line=$(grep -n 'SAFETY:' "$restore_tmp/ok.log" | head -1 | cut -d: -f1)
stop_line=$(grep -n 'Parando' "$restore_tmp/ok.log" | head -1 | cut -d: -f1)
assert_eq 'restore: el respaldo de seguridad va antes de parar' 'antes' \
    "$(if [ -n "$safety_line" ] && [ -n "$stop_line" ] && [ "$safety_line" -lt "$stop_line" ]; then echo antes; else echo despues; fi)"

# --- El restore falla: los servicios se levantan igual --------------------

: > "$restore_tmp/systemctl.log"
(
    restore_env
    MODE=restore
    RESTORE_FILE='bueno.dump'
    resolve_backup_file() { printf '%s\n' "$DB_BACKUP_DIR/$RESTORE_FILE"; }
    db_dump() { printf 'x' > "$1"; }
    db_restore() { return 1; }
    eval "$restore_mode_block"
) >"$restore_tmp/fail.log" 2>&1
fail_rc=$?
fail_log=$(cat "$restore_tmp/fail.log")

assert_eq 'restore: un restore fallido sale 1' 1 "$fail_rc"
assert_contains 'restore: un restore fallido deja estado failed' 'STATUS:restore:failed' \
    "$fail_log"
# Lo que hace recuperable el fallo: el panel vuelve a responder y el operador
# puede restaurar el respaldo de seguridad sin entrar por SSH.
assert_contains 'restore: un restore fallido levanta los servicios' \
    'start webcmp webcmp-huey' "$(cat "$restore_tmp/systemctl.log")"

# --- Sin peticion en disco: no hace nada ----------------------------------

(
    restore_env
    MODE=restore-request
    eval "$restore_mode_block"
) >"$restore_tmp/no-request.log" 2>&1
assert_eq 'restore: sin peticion sale 1' 1 "$?"
assert_contains 'restore: sin peticion lo explica' 'no hay nada que restaurar' \
    "$(cat "$restore_tmp/no-request.log")"

rm -rf "$restore_tmp"
