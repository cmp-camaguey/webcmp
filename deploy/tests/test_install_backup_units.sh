# Instalador del respaldo diario (deploy/install-backup-units.sh).
#
# Lo que importa probar es el contrato que sostiene el diseno:
#
#   1. El render sustituye LITERALMENTE: `webcmp` como patron tambien matchearia
#      `webcmp-huey`, y un unit con el nombre del otro servicio no falla al
#      instalarse, falla la noche en que el respaldo no corre.
#   2. El timer se habilita y el servicio NO se arranca: el servicio lo dispara
#      el timer, y arrancarlo aca haria un dump que nadie pidio.
#   3. Con DRY_RUN no se toca nada.
#
# La instalacion real (modos, dueno root) se ejercita solo como root: `install -o
# root -g root` no se puede probar desde una cuenta normal.
#
# Se ejecuta con `source` desde run.sh; no se corre solo.

BACKUP_INSTALL_SH=$REPO_ROOT/deploy/install-backup-units.sh

# Los units de origen se llaman como en el repo (`webcmp-backup.*`); solo cambia
# el nombre del DESTINO. Buscar `$BACKUP_UNIT` dentro del checkout falla con
# cualquier nombre configurado.
assert_not_contains 'backup: no busca el unit de origen con el nombre del destino' \
    'deploy/systemd/$BACKUP_UNIT' "$(cat "$BACKUP_INSTALL_SH")"

backup_pure=$(require_block unit-files "$BACKUP_INSTALL_SH")
backup_main=$(require_block install-backup-units "$BACKUP_INSTALL_SH")

backup_tmp=$(mktemp -d)

# --- Render: sustitucion literal, sin regex -------------------------------

(
    eval "$backup_pure"
    render_unit "$REPO_ROOT/deploy/systemd/webcmp-backup.service" \
        "$backup_tmp/service" \
        '/srv/webcmp<>/opt/cmp' \
        'ExecStart=/usr/local/sbin/webcmp-deploy<>ExecStart=/opt/bin/webcmp-deploy'
    render_unit "$REPO_ROOT/deploy/systemd/webcmp-backup.timer" \
        "$backup_tmp/timer" \
        'Unit=webcmp-backup.service<>Unit=cmp-respaldo.service'
) || true

service_rendered=$(cat "$backup_tmp/service" 2>/dev/null || true)
timer_rendered=$(cat "$backup_tmp/timer" 2>/dev/null || true)

assert_contains 'backup: el servicio apunta al ejecutable configurado' \
    'ExecStart=/opt/bin/webcmp-deploy --backup' "$service_rendered"
assert_contains 'backup: el servicio conserva el modo --backup' \
    '--backup' "$service_rendered"
assert_contains 'backup: el timer apunta al servicio configurado' \
    'Unit=cmp-respaldo.service' "$timer_rendered"
assert_contains 'backup: el timer es persistente' 'Persistent=true' "$timer_rendered"
assert_not_contains 'backup: el servicio no conserva la ruta del checkout' \
    '/srv/webcmp' "$service_rendered"

# --- Guardas de entrada ---------------------------------------------------

(
    eval "$backup_pure"
    eval "$backup_main"
    APP_DIR=$backup_tmp/nope
    BACKUP_UNIT=webcmp-backup
    DEPLOY_SCRIPT=$backup_tmp/deploy
    UNIT_DIR=$backup_tmp/units
    SYSTEMCTL=true
    DRY_RUN=0
    install_backup_units
) >"$backup_tmp/guard.log" 2>&1
guard_rc=$?
assert_eq 'backup: sin el checkout se niega' 1 "$guard_rc"
assert_contains 'backup: nombra la pieza que falta' 'webcmp-backup.service' \
    "$(cat "$backup_tmp/guard.log")"

mkdir -p "$backup_tmp/app/deploy/systemd" "$backup_tmp/units"
cp "$REPO_ROOT/deploy/systemd/webcmp-backup.service" "$backup_tmp/app/deploy/systemd/"
cp "$REPO_ROOT/deploy/systemd/webcmp-backup.timer" "$backup_tmp/app/deploy/systemd/"

(
    eval "$backup_pure"
    eval "$backup_main"
    APP_DIR=$backup_tmp/app
    BACKUP_UNIT=webcmp-backup
    DEPLOY_SCRIPT=$backup_tmp/no-existe
    UNIT_DIR=$backup_tmp/units
    SYSTEMCTL=true
    DRY_RUN=0
    install_backup_units
) >"$backup_tmp/no-exec.log" 2>&1
no_exec_rc=$?
assert_eq 'backup: sin el ejecutable del deploy se niega' 1 "$no_exec_rc"
assert_contains 'backup: explica quien instala el ejecutable' 'deploy/install.sh' \
    "$(cat "$backup_tmp/no-exec.log")"

# --- DRY_RUN: imprime y no escribe ----------------------------------------

touch "$backup_tmp/deploy"
chmod +x "$backup_tmp/deploy"

(
    eval "$backup_pure"
    eval "$backup_main"
    APP_DIR=$backup_tmp/app
    BACKUP_UNIT=webcmp-backup
    DEPLOY_SCRIPT=$backup_tmp/deploy
    UNIT_DIR=$backup_tmp/units
    SYSTEMCTL=true
    CONFIG=$backup_tmp/deploy.env
    DRY_RUN=1
    install_backup_units
) >"$backup_tmp/dry.log" 2>&1
assert_eq 'backup: dry-run sale 0' 0 "$?"
assert_contains 'backup: dry-run imprime la habilitacion del timer' \
    'enable --now webcmp-backup.timer' "$(cat "$backup_tmp/dry.log")"
assert_eq 'backup: dry-run no escribe unidades' '0' \
    "$(find "$backup_tmp/units" -type f | wc -l | tr -d ' ')"

# --- Instalacion completa (solo como root) --------------------------------

if [ "$(id -u)" -ne 0 ]; then
    printf '  omitido  instalacion real del timer: la suite no corre como root\n'
else
    mkdir -p "$backup_tmp/bin"
    cat > "$backup_tmp/bin/systemctl" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
exit 0
STUB
    chmod +x "$backup_tmp/bin/systemctl"

    backup_install_run() {
        (
            APP_DIR=$backup_tmp/app
            BACKUP_UNIT=webcmp-backup
            DEPLOY_SCRIPT=$backup_tmp/deploy
            UNIT_DIR=$backup_tmp/units
            SYSTEMCTL=$backup_tmp/bin/systemctl
            CONFIG=$backup_tmp/deploy.env
            DRY_RUN=0
            STUB_LOG=$backup_tmp/systemctl.log
            export STUB_LOG
            eval "$backup_pure"
            eval "$backup_main"
            install_backup_units
        ) >"$backup_tmp/out.log" 2>&1
    }

    backup_install_run
    assert_eq 'instalacion: sale 0' 0 "$?"
    assert_eq 'instalacion: el servicio queda root:root 644' 'root:root 644' \
        "$(stat -c '%U:%G %a' "$backup_tmp/units/webcmp-backup.service" 2>/dev/null || true)"
    assert_eq 'instalacion: el timer queda root:root 644' 'root:root 644' \
        "$(stat -c '%U:%G %a' "$backup_tmp/units/webcmp-backup.timer" 2>/dev/null || true)"
    assert_contains 'instalacion: recarga systemd' 'daemon-reload' \
        "$(cat "$backup_tmp/systemctl.log")"
    assert_contains 'instalacion: habilita el timer' \
        'enable --now webcmp-backup.timer' "$(cat "$backup_tmp/systemctl.log")"
    assert_not_contains 'instalacion: no arranca el servicio' \
        'start webcmp-backup.service' "$(cat "$backup_tmp/systemctl.log")"

    before=$(stat -c '%Y %s' "$backup_tmp/units/webcmp-backup.timer")
    sleep 1
    backup_install_run
    assert_eq 'instalacion: la segunda corrida no reescribe el timer' "$before" \
        "$(stat -c '%Y %s' "$backup_tmp/units/webcmp-backup.timer")"
fi

rm -rf "$backup_tmp"
