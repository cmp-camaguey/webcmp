#!/usr/bin/env bash
# Sincroniza artefactos root desde un espejo bare del repo.
#
# Uso:
#   webcmp-deploy-sync.sh [--quiet] [--sha <sha>]
#
# Si no se pasa --sha, se resuelve desde refs/heads/main del espejo.
# Extrae el manifest y todos los archivos del SHA especificado.
# Si falla la sincronización, no toca nada instalado y el deploy sigue
# (fail-open: el script anterior sigue siendo root-owned y conocido).

set -Eeuo pipefail
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
SYNC_STATE_DIR=${SYNC_STATE_DIR:-/var/lib/webcmp}
SYNC_MIRROR="$SYNC_STATE_DIR/webcmp-sync.mirror"
SYNC_STATE_FILE="$SYNC_STATE_DIR/deploy-sync.json"
BRANCH_REF=${BRANCH_REF:-refs/heads/main}
REMOTE_URL=${REMOTE_URL:-https://github.com/cmp-camaguey/webcmp.git}
current_sha=""
QUIET=0
REFRESH=0

# Variables de render (defaults para un servidor tipico; sobreescribibles)
APP_DIR=${APP_DIR:-/srv/webcmp}
SERVICE_USER=${SERVICE_USER:-webcmp}
SERVICE_GROUP=${SERVICE_GROUP:-webcmp}
GUNICORN_UNIT=${GUNICORN_UNIT:-webcmp}
HUEY_UNIT=${HUEY_UNIT:-webcmp-huey}
ENCRYPTION_ENV=${ENCRYPTION_ENV:-/etc/webcmp/encryption.env}

# El mensaje termina en el estado del sync, asi que `die` lo deja grabado:
# el panel no lo reenvia, pero el archivo no sirve de nada si no dice porque
# fallo. Un fallo que no pasa por aca lo captura el ERR trap.
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33mAVISO:\033[0m %s\n' "$*" >&2; }
# El timeout lo manda systemd. Sin esto el script muere con SIGTERM y el EXIT
# trap no corre: no quedaria ningun registro del fallo.
trap 'exit 143' TERM INT

# --- Estado del ultimo sync (exitoso o fallido) ---
#
# El timer es la unica forma habitual de que el sync corra, y si no corre a
# diario nadie se entera: el deploy es fail-open y los artefactos root viejos
# siguen funcionando. Este archivo es la pista del panel, asi que tiene que
# decir tambien cuando el intento fallo, no solo cuando termino bien.
#
# Se define y se engancha aca, antes de tocar el espejo: la mayoria de los
# fallos ocurren antes de instalar nada, y sin el trap puesto en ese punto no
# quedaria ningun registro de ellos.
TMP_DIR=""
# Se pone en 1 justo despues de escribir el estado bueno. Un fallo posterior a
# ese punto no puede reescribirlo: el estado quedaria "failed" con artefactos ya
# instalados, y el panel avisaria de algo que quedo resuelto.
SYNC_STATE_OK=0

write_sync_failure() {
    local failed_at prev_sha prev_at tmp
    failed_at=$(date -Is)
    prev_sha=""
    prev_at=""
    if [ -f "$SYNC_STATE_FILE" ]; then
        prev_sha=$(grep -o '"sha":"[^"]*"' "$SYNC_STATE_FILE" 2>/dev/null | head -1 | cut -d'"' -f4 || true)
        prev_at=$(grep -o '"installed_at":"[^"]*"' "$SYNC_STATE_FILE" 2>/dev/null | head -1 | cut -d'"' -f4 || true)
    fi
    # Sin texto libre del error: el archivo lo escribe root y lo leen el panel y
    # `deploy.sh --check`, ninguno de los dos puede mostrar la causa. El detalle
    # es del journal. Solo se anota que fallo, cuando, y que quedo instalado.
    #
    # Sin `install -o root`: el script corre como root en produccion, y
    # `install` en un test de usuario no puede poner el dueno a mano. En
    # produccion el dueno queda igual, porque quien escribe es root.
    tmp="$SYNC_STATE_FILE.tmp.$$"
    if printf '{"status":"failed","failed_at":"%s","sha":"%s","installed_at":"%s"}\n' \
        "$failed_at" "$prev_sha" "$prev_at" > "$tmp" 2>/dev/null; then
        chmod 0644 "$tmp" 2>/dev/null || true
        if [ "$(id -u)" -eq 0 ]; then
            chown root:root "$tmp" 2>/dev/null || true
        fi
        mv -T "$tmp" "$SYNC_STATE_FILE" 2>/dev/null || true
    fi
    rm -f "$tmp" 2>/dev/null || true
}

on_exit() {
    local code=$?
    if [ -n "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
    if [ "$code" -ne 0 ] && [ "$SYNC_STATE_OK" -eq 0 ]; then
        write_sync_failure
    fi
    return 0
}
trap on_exit EXIT
# `if` y no `[ ] && printf`: con --quiet el `[ ]` falla y la funcion devuelve 1,
# que bajo `set -Eeuo pipefail` mata el script en el primer log.
# Las dos llamadas reales usan --quiet (install-deploy-sync.sh y deploy.sh),
# asi que el sync salia sin instalar nada.
log() {
    if [ "$QUIET" -eq 0 ]; then
        printf '\n\033[1;34m==>\033[0m %s\n' "$*"
    fi
    return 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --quiet) QUIET=1 ;;
        --sha) shift; current_sha="${1:-}" ;;
        --refresh) REFRESH=1 ;;
        --help)
            printf '%s [--quiet] [--sha <sha>] [--refresh]\n' "$SCRIPT_NAME"
            printf '  --sha <sha>   Extrae del SHA especificado (default: refs/heads/main)\n'
            printf '  --refresh     Actualiza el espejo antes de extraer\n'
            exit 0 ;;
        *) die "Opcion desconocida: $1" ;;
    esac
    shift
done

# --- Verificar espejo root ---

[ -d "$SYNC_MIRROR/objects" ] || die "Espejo root no existe en $SYNC_MIRROR. Ejecute install-deploy-sync.sh primero."

# --- Actualizar espejo si --refresh ---

if [ "$REFRESH" -eq 1 ]; then
    log "Actualizando espejo desde $REMOTE_URL ($BRANCH_REF)"
    # El refspec NECESITA destino (`origen:origen`). Sin el, en un bare el fetch
    # solo actualiza FETCH_HEAD: no crea ni mueve refs/heads/main, y el timer
    # (que corre sin --sha) resolveria para siempre el SHA viejo.
    git -C "$SYNC_MIRROR" fetch --quiet origin "$BRANCH_REF:$BRANCH_REF" \
        || warn "No se pudo actualizar el espejo"
fi

# --- Resolver SHA ---

if [ -z "$current_sha" ]; then
    current_sha=$(git -C "$SYNC_MIRROR" rev-parse "$BRANCH_REF" 2>/dev/null || true)
    [ -n "$current_sha" ] || die "No se pudo resolver $BRANCH_REF del espejo."
    log "SHA resuelto: $current_sha"
else
    log "SHA explicito: $current_sha"
fi

# --- Render literal (sin regex, igual que install.sh) ---

render_content() {
    local content="$1"
    content="${content//\/srv\/webcmp/$APP_DIR}"
    content="${content//\/etc\/webcmp\/encryption.env/$ENCRYPTION_ENV}"
    content="${content//webcmp-huey/$HUEY_UNIT}"
    content="${content//User=webcmp/User=$SERVICE_USER}"
    content="${content//Group=webcmp/Group=$SERVICE_GROUP}"
    content="${content//RuntimeDirectory=webcmp/RuntimeDirectory=$GUNICORN_UNIT}"
    content="${content//\/run\/webcmp/\/run\/$GUNICORN_UNIT}"
    printf '%s' "$content"
}

# --- Extraer manifest del SHA ---

TMP_DIR=$(mktemp -d)

manifest_tmp="$TMP_DIR/manifest"
git -C "$SYNC_MIRROR" show "$current_sha:deploy/root-bundle.manifest" > "$manifest_tmp" 2>/dev/null \
    || die "No se pudo extraer root-bundle.manifest del SHA $current_sha."

# Crea el directorio destino si falta. `install` no crea los padres, y hay
# destinos que solo existian despues de correr install.sh:
# /var/www/webcmp-errors es el caso real (la pagina 50x). En un servidor ya
# instalado, el primer deploy que traiga un archivo nuevo moriria con un
# "No such file or directory" que no dice que falta el directorio.
ensure_dest_dir() {
    local dest_dir
    dest_dir=$(dirname "$1")
    [ -d "$dest_dir" ] || install -d -m 0755 -o root -g root "$dest_dir"
}

# --- Instalar archivos ---

installed=0
# Los campos van separados por espacios o tabuladores: el manifest se alinea
# con espacios para que se lea. Se exigen EXACTAMENTE cuatro: una linea con un
# campo de mas casi siempre es un path con un espacio, y partirlo a la
# ambiguedad dejaria el destino en un lugar que nadie reviso.
while read -r src_path dest_path mode owner_group extra; do
    # Saltar lineas vacias o comentarios
    [ -n "${src_path:-}" ] || continue
    [[ "$src_path" == \#* ]] && continue

    if [ -n "${extra:-}" ] || [ -z "${dest_path:-}" ] || [ -z "${mode:-}" ] || [ -z "${owner_group:-}" ]; then
        die "Entrada mal formada en root-bundle.manifest (se esperaban 4 campos): ${src_path:-} ${dest_path:-} ${mode:-} ${owner_group:-} ${extra:-}"
    fi

    tmp_file="$TMP_DIR/$(echo "$src_path" | tr '/' '_')"

    # Extraer del espejo (NUNCA del checkout)
    git -C "$SYNC_MIRROR" show "$current_sha:$src_path" > "$tmp_file" 2>/dev/null \
        || { rm -f "$tmp_file"; die "No se pudo extraer $src_path del SHA $current_sha"; }

    # Renderizar units systemd (.timer incluido: install.sh los renderiza, y un
    # Documentation=/srv/webcmp/... apuntando al directorio equivocado en un
    # server con otro APP_DIR queda instalado sin que nadie lo note)
    if [[ "$src_path" == *systemd/*.service || "$src_path" == *systemd/*.path || "$src_path" == *systemd/*.timer ]]; then
        content=$(cat "$tmp_file")
        printf '%s' "$(render_content "$content")" > "$tmp_file"
    fi

    # Validar scripts
    if [[ "$src_path" == *.sh ]]; then
        bash -n "$tmp_file" || die "bash -n fallo en $src_path (SHA $current_sha)"
    fi

    # Instalar atomicamente
    ensure_dest_dir "$dest_path"
    install -m "$mode" -o "${owner_group%%:*}" -g "${owner_group##*:}" \
        "$tmp_file" "$dest_path.tmp.$$"
    mv -T "$dest_path.tmp.$$" "$dest_path"
    log "Instalado $dest_path ($mode)"
    installed=$((installed + 1))
done < "$manifest_tmp"

# --- daemon-reload si cambio alguna unidad ---

if [ "$installed" -gt 0 ]; then
    systemctl daemon-reload || warn "daemon-reload fallo (las units nuevas no se ven hasta el proximo reboot)"
fi

# --- Escribir estado atomico ---

installed_at=$(date -Is)
state_tmp="$TMP_DIR/state.json"
printf '{"status":"ok","sha":"%s","installed_at":"%s","from":"%s","installed":%d}\n' \
    "$current_sha" "$installed_at" "$BRANCH_REF" "$installed" > "$state_tmp"
install -m 0644 -o root -g root "$state_tmp" "$SYNC_STATE_FILE"
SYNC_STATE_OK=1

log "Sync completado: $installed archivos, SHA $current_sha, $installed_at"
