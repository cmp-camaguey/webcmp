#!/usr/bin/env bash
# Instala el espejo root y el timer de sync para deploy.
#
# Uso:
#   sudo bash deploy/install-deploy-sync.sh [--dry-run]
#
# Crea:
#   - /var/lib/webcmp-sync.mirror (espejo bare del repo, root:root 0700)
#   - /usr/local/sbin/webcmp-deploy-sync.sh (helper de sync, root:root 0755)
#   - /etc/systemd/system/webcmp-sync.{service,timer} (timer diario)
#
# Es idempotente: una segunda corrida no cambia nada si los archivos ya estan.

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
SYNC_STATE_DIR=${SYNC_STATE_DIR:-/var/lib/webcmp}
SYNC_MIRROR="$SYNC_STATE_DIR/webcmp-sync.mirror"
REMOTE_URL=${REMOTE_URL:-https://github.com/cmp-camaguey/webcmp.git}
BRANCH_REF=${BRANCH_REF:-refs/heads/main}
DRY_RUN=${DRY_RUN:-0}

die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33mAVISO:\033[0m %s\n' "$*" >&2; }
log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        *) die "Opcion desconocida: $1" ;;
    esac
    shift
done

if [ "$DRY_RUN" -eq 1 ]; then
    log "Dry-run: mostrando comandos sin ejecutar"
fi

# --- 1. Directorio de estado (compartido, no se tocan permisos) ---

# SYNC_STATE_DIR (default /var/lib/webcmp) NO es del sync: en el mismo directorio
# viven deploy-request (que escribe el proceso web para pedir un deploy) y
# deploy-status.json. install.sh lo deja en 2775 deploy:webcmp. Si aqui se
# impusiera 0700 root:root, el boton "Actualizar" del panel moria con
# "El servidor no acepta peticiones de despliegue" y nadie lo veria (ocurrio en
# produccion tras el bootstrap de v0.7.7). Si falta, se crea como lo deja
# install.sh; si existe, no se cambia nada.
STATE_OWNER=${STATE_OWNER:-deploy}
STATE_GROUP=${STATE_GROUP:-webcmp}
if [ -d "$SYNC_STATE_DIR" ]; then
    log "Directorio de estado ya existe: $SYNC_STATE_DIR (permisos intactos)"
elif [ "$DRY_RUN" -eq 1 ]; then
    printf "  install -d -m 2775 -o %s -g %s %s\n" "$STATE_OWNER" "$STATE_GROUP" "$SYNC_STATE_DIR"
else
    install -d -m 2775 -o "$STATE_OWNER" -g "$STATE_GROUP" "$SYNC_STATE_DIR" \
        || die "No se pudo crear $SYNC_STATE_DIR con dueno $STATE_OWNER:$STATE_GROUP. Corre install.sh primero."
    log "Directorio creado: $SYNC_STATE_DIR ($STATE_OWNER:$STATE_GROUP 2775)"
fi

# --- 2. Crear espejo bare del repo ---

if [ -d "$SYNC_MIRROR/objects" ]; then
    log "Espejo ya existe en $SYNC_MIRROR (actualizando)"
    if [ "$DRY_RUN" -eq 0 ]; then
        # Refspec con destino: sin el, en un bare el fetch no crea ni mueve
        # refs/heads/main y el timer resolveria el SHA viejo.
        git -C "$SYNC_MIRROR" fetch --quiet origin "$BRANCH_REF:$BRANCH_REF" \
            || warn "No se pudo actualizar el espejo"
    fi
else
    log "Creando espejo bare en $SYNC_MIRROR"
    if [ "$DRY_RUN" -eq 1 ]; then
        printf "  git init --bare %s\n" "$SYNC_MIRROR"
        printf "  git -C %s remote add origin %s\n" "$SYNC_MIRROR" "$REMOTE_URL"
        printf "  git -C %s fetch origin %s:%s\n" "$SYNC_MIRROR" "$BRANCH_REF" "$BRANCH_REF"
    else
        tmp_mirror=$(mktemp -d)
        trap 'rm -rf "$tmp_mirror"' EXIT
        git init --bare "$tmp_mirror" >/dev/null 2>&1
        git -C "$tmp_mirror" remote add origin "$REMOTE_URL" >/dev/null 2>&1
        git -C "$tmp_mirror" fetch --quiet origin "$BRANCH_REF:$BRANCH_REF" >/dev/null 2>&1
        mv -f "$tmp_mirror" "$SYNC_MIRROR"
        chmod 0700 "$SYNC_MIRROR"
        chown root:root "$SYNC_MIRROR"
        log "Espejo creado y actualizado"
    fi
fi

# --- 3. Instalar el helper de sync ---

sync_script="$REPO_ROOT/deploy/webcmp-deploy-sync.sh"
if [ ! -f "$sync_script" ]; then
    die "No se encontro $sync_script"
fi

if [ "$DRY_RUN" -eq 1 ]; then
    printf "  install -m 0755 -o root -g root %s /usr/local/sbin/webcmp-deploy-sync.sh\n" "$sync_script"
else
    install -m 0755 -o root -g root "$sync_script" /usr/local/sbin/webcmp-deploy-sync.sh
    log "Helper instalado: /usr/local/sbin/webcmp-deploy-sync.sh"
fi

# --- 4. Instalar unidades systemd ---

unit_dir=/etc/systemd/system
systemd_dir="$REPO_ROOT/deploy/systemd"

for unit in webcmp-sync.service webcmp-sync.timer; do
    src="$systemd_dir/$unit"
    dest="$unit_dir/$unit"
    if [ ! -f "$src" ]; then
        die "No se encontro $src"
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        printf "  install -m 0644 -o root -g root %s %s\n" "$src" "$dest"
    else
        install -m 0644 -o root -g root "$src" "$dest"
        log "Unidad instalada: $dest"
    fi
done

if [ "$DRY_RUN" -eq 0 ]; then
    log "Recargando systemd"
    systemctl daemon-reload
    log "Habilitando timer webcmp-sync.timer"
    systemctl enable webcmp-sync.timer
    log "Iniciando timer webcmp-sync.timer"
    systemctl start webcmp-sync.timer
    log "Ejecutando sync inicial"
    /usr/local/sbin/webcmp-deploy-sync.sh --quiet
fi

log "Instalacion completada. El timer corre diariamente para mantener el espejo actualizado."
