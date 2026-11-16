#!/usr/bin/env bash
#
# Instala el respaldo diario de la base: `webcmp-backup.service` y
# `webcmp-backup.timer`.
#
# Por que existe si `install.sh` ya los instala: `install.sh` es un instalador
# completo — pips, migraciones, .env, preguntas — y no se vuelve a correr en un
# servidor que ya esta sirviendo. Las unidades systemd no viajan con el deploy:
# `deploy.sh` actualiza el checkout y reinicia los servicios, y a proposito no
# escribe en /etc/systemd/system, porque el checkout lo escribe el usuario del
# sitio.
#
# De ahi sale el agujero que este script cierra: un servidor se actualiza a un
# commit que agrega una unidad que nunca se instalo. `deploy.sh` se niega a
# desplegar en ese estado y manda aca.
#
# Es idempotente y no interactivo. No toca el .env, ni la base, ni el venv, ni el
# codigo: instala dos archivos, recarga systemd y habilita el timer.
#
# Uso:
#   sudo bash deploy/install-backup-units.sh
#   sudo bash deploy/install-backup-units.sh --help
#
# Variables (mismos nombres y defaults que install.sh y deploy.env):
#   APP_DIR, CONFIG_DIR, CONFIG, BACKUP_UNIT, DEPLOY_SCRIPT, SYSTEMCTL,
#   UNIT_DIR, DRY_RUN
#
set -Eeuo pipefail

CONFIG_DIR=${CONFIG_DIR:-/etc/webcmp}
CONFIG=${CONFIG:-$CONFIG_DIR/deploy.env}
# Un `source` de un archivo que no existe es un error con `set -e`, y este script
# tiene que poder correr en un servidor donde deploy.env no esta.
if [ -r "$CONFIG" ]; then
    # shellcheck disable=SC1090
    source "$CONFIG"
fi

: "${APP_DIR:=/srv/webcmp}"
: "${BACKUP_UNIT:=webcmp-backup}"
: "${DEPLOY_SCRIPT:=/usr/local/sbin/webcmp-deploy}"
: "${SYSTEMCTL:=systemctl}"
: "${UNIT_DIR:=/etc/systemd/system}"
: "${DRY_RUN:=0}"

# >>> TEST-BLOCK: unit-files
log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Renderiza `src` en `dest` sustituyendo pares `viejo<>nuevo`.
#
# Las rutas de /srv/webcmp y el nombre del ejecutor estan escritos en los unit a
# proposito (en un unit, `APP_DIR=/srv/webcmp` no es una clave valida de
# systemd), asi que un checkout o un ejecutor en otra ruta necesitan reescribir
# el archivo. El reemplazo es literal —el patron va entre comillas en
# `${var//patron/texto}`—, no un regex: `webcmp` como patron tambien matchearia
# `webcmp-huey`.
render_unit() {
    local src=$1 dest=$2 line out pair old new
    shift 2
    : > "$dest"
    while IFS= read -r line || [ -n "$line" ]; do
        out=$line
        for pair in "$@"; do
            old=${pair%%<>*}
            new=${pair#*<>}
            out=${out//"$old"/"$new"}
        done
        printf '%s\n' "$out" >> "$dest"
    done < "$src"
}

# Todo lo que muta el sistema pasa por aca: con DRY_RUN se imprime y no se
# ejecuta, que es lo unico que hace util el modo en un servidor real.
run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '  [dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

# `install`, pero solo si el destino no es ya identico. Reescribir un archivo
# identico cambia su mtime sin motivo y hace que "no cambio nada" sea imposible
# de comprobar desde la salida.
install_if_changed() {
    local src=$1 dest=$2 mode=$3 owner=${4:-root} group=${5:-root}
    # `10#` quita los ceros de la izquierda: se pide `0644` y `stat -c %a`
    # devuelve `644`, asi que sin esto la comparacion nunca puede ser cierta.
    if [ -f "$dest" ] && cmp -s "$src" "$dest" \
        && [ "$(stat -c '%U:%G %a' "$dest")" = "$owner:$group $((10#$mode))" ]
    then
        printf '  %s ya esta al dia (%s:%s %s)\n' "$dest" "$owner" "$group" "$((10#$mode))"
        return 0
    fi
    run install -o "$owner" -g "$group" -m "$mode" "$src" "$dest"
}

# Renderiza un unit del checkout y lo instala con su modo definitivo.
install_unit() {
    local src=$1 dest=$2 tmp
    shift 2
    tmp=$(mktemp)
    render_unit "$src" "$tmp" "$@"
    install_if_changed "$tmp" "$dest" 0644
    rm -f "$tmp"
}
# <<< TEST-BLOCK: unit-files

usage() {
    cat <<'EOF'
Instala el respaldo diario de la base.

  sudo bash deploy/install-backup-units.sh

Instala las unidades webcmp-backup.service y webcmp-backup.timer, recarga
systemd y habilita el timer. No toca el .env, la base, el venv ni el codigo.
Idempotente: una segunda corrida no reescribe nada.

Variables: APP_DIR, CONFIG, BACKUP_UNIT, DEPLOY_SCRIPT, UNIT_DIR, DRY_RUN=1.
EOF
}

if [ "${1:-}" = '--help' ] || [ "${1:-}" = '-h' ]; then
    usage
    exit 0
fi
[ $# -eq 0 ] || die "Opcion desconocida: $1 (--help para el uso)."

[ "$(id -u)" -eq 0 ] || die "Este script necesita root: escribe en /etc/systemd/system y habilita unidades."

# >>> TEST-BLOCK: install-backup-units
#
# El trabajo privilegiado, en una funcion, para que las pruebas lo puedan
# ejercitar de punta a punta con un arbol temporal y un `systemctl` de mentira.
install_backup_units() {
    local piece

    # Los nombres de ORIGEN son los del repositorio y no cambian: `install.sh`
    # renderiza `deploy/systemd/webcmp-backup.service` a
    # `/etc/systemd/system/$BACKUP_UNIT.service`. Buscar `$BACKUP_UNIT.service`
    # dentro del checkout fallaria con cualquier nombre configurado.
    for piece in "$APP_DIR/deploy/systemd/webcmp-backup.service" \
        "$APP_DIR/deploy/systemd/webcmp-backup.timer"
    do
        [ -f "$piece" ] \
            || die "No existe $piece. Corre el script desde el checkout (APP_DIR=$APP_DIR)."
    done

    # El ejecutable lo instala el andamiaje del deploy; si no esta, el timer
    # correria una unidad que falla todas las noches sin que nadie mire.
    [ -x "$DEPLOY_SCRIPT" ] \
        || die "No existe $DEPLOY_SCRIPT. Lo instala deploy/install.sh; sin el, el timer no tiene que ejecutar."

    log "Respaldo diario de la base"

    log 'Unidades systemd'
    install_unit "$APP_DIR/deploy/systemd/webcmp-backup.service" \
        "$UNIT_DIR/$BACKUP_UNIT.service" \
        "/srv/webcmp<>$APP_DIR" \
        "ExecStart=/usr/local/sbin/webcmp-deploy<>ExecStart=$DEPLOY_SCRIPT"

    install_unit "$APP_DIR/deploy/systemd/webcmp-backup.timer" \
        "$UNIT_DIR/$BACKUP_UNIT.timer" \
        "/srv/webcmp<>$APP_DIR" \
        "Unit=webcmp-backup.service<>Unit=$BACKUP_UNIT.service"

    run "$SYSTEMCTL" daemon-reload
    # `enable --now` sobre el timer: el servicio lo dispara el timer. Arrancarlo
    # ahora haria un respaldo que nadie pidio en este momento.
    run "$SYSTEMCTL" enable --now "$BACKUP_UNIT.timer"

    if [ "$DRY_RUN" -eq 0 ]; then
        "$SYSTEMCTL" is-active --quiet "$BACKUP_UNIT.timer" \
            || die "El timer no quedo activo. Revisa: $SYSTEMCTL status $BACKUP_UNIT.timer"
    fi

    log 'Listo'
    printf '  unidad:  %s (diario, 03:15 hora local)\n' "$BACKUP_UNIT.timer"
    printf '  ejecuta: %s --backup\n' "$DEPLOY_SCRIPT"
    printf '  destino: DB_BACKUP_DIR de %s\n' "$CONFIG"
    printf '  logs:    journalctl -u %s\n' "$BACKUP_UNIT"
}
# <<< TEST-BLOCK: install-backup-units

install_backup_units
