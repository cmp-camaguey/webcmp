#!/usr/bin/env bash
# Tests de webcmp-deploy-sync.sh e install-deploy-sync.sh.
#
# No tocan el sistema real: usan un espejo bare temporal creado del repo local
# y un SYNC_STATE_DIR temporal. Verifican: --help, fallos cerrados, extraccion
# del SHA, render de units, estado JSON, y el enganche en deploy.sh/install.sh.

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/../.."
source "$SCRIPT_DIR/lib.sh"

TEST_TMP=$(mktemp -d "${TMPDIR:-/tmp}/webcmp-sync-tests.XXXXXX")
trap 'rm -rf "$TEST_TMP"' EXIT

SYNC_STATE_DIR="$TEST_TMP/state"
mkdir -p "$SYNC_STATE_DIR"
SYNC_MIRROR="$SYNC_STATE_DIR/webcmp-sync.mirror"
export SYNC_STATE_DIR

SYNC_SCRIPT="$REPO_ROOT/deploy/webcmp-deploy-sync.sh"
INSTALL_SYNC="$REPO_ROOT/deploy/install-deploy-sync.sh"
DEPLOY_SH="$REPO_ROOT/deploy/deploy.sh"
INSTALL_SH="$REPO_ROOT/deploy/install.sh"

# Espejo bare del repo local, con la rama dev: mismo formato que el espejo
# root del servidor (origin + refs/heads/...).
setup_mirror() {
    git init --bare "$SYNC_MIRROR" >/dev/null 2>&1
    git -C "$SYNC_MIRROR" remote add origin "$REPO_ROOT" >/dev/null 2>&1
    # Se trae el HEAD del checkout actual (la rama de feature), no una rama
    # fija: los tests verifican el manifiesto de ESTA rama, no el de dev.
    local head_sha
    head_sha=$(git -C "$REPO_ROOT" rev-parse HEAD)
    git -C "$SYNC_MIRROR" fetch --quiet "$REPO_ROOT" "$head_sha" >/dev/null 2>&1
    git -C "$SYNC_MIRROR" update-ref refs/heads/main "$head_sha"
}

# --- install-deploy-sync.sh --dry-run --------------------------------------

set +e
install_dry=$(bash "$INSTALL_SYNC" --dry-run 2>&1)
install_dry_rc=$?
set -e
assert_eq 'install-deploy-sync.sh --dry-run sale 0' 0 "$install_dry_rc"
assert_contains 'install-deploy-sync.sh --dry-run nombra el espejo' \
    'webcmp-sync.mirror' "$install_dry"
assert_contains 'install-deploy-sync.sh --dry-run nombra el helper' \
    'webcmp-deploy-sync.sh' "$install_dry"
assert_contains 'install-deploy-sync.sh --dry-run nombra el timer' \
    'webcmp-sync.timer' "$install_dry"

# --- webcmp-deploy-sync.sh --help ------------------------------------------

set +e
sync_help=$(bash "$SYNC_SCRIPT" --help 2>&1)
sync_help_rc=$?
set -e
assert_eq 'webcmp-deploy-sync.sh --help sale 0' 0 "$sync_help_rc"
assert_contains 'webcmp-deploy-sync.sh --help nombra --sha' '--sha' "$sync_help"
assert_contains 'webcmp-deploy-sync.sh --help nombra --refresh' '--refresh' "$sync_help"

# --- log() con --quiet no aborta bajo set -e --------------------------------

sync_src=$(cat "$SYNC_SCRIPT")

# Regresion: log() era `[ "$QUIET" -eq 0 ] && printf ...`. Con --quiet el test
# falla, la funcion devuelve 1 y `set -Eeuo pipefail` mata el script en el
# PRIMER log: el sync salia en silencio sin instalar nada. Afectaba a las dos
# llamadas reales, que usan --quiet: el sync inicial de install-deploy-sync.sh
# y el que hace deploy.sh tras el checkout.
#
# No se puede correr el helper completo sin root (el manifest instala en
# /usr/local/sbin y con -o root), asi que se pina el contrato de la funcion.
log_fn=$(awk '/^log\(\) \{/{f=1} f{print} f && /^}$/{exit}' "$SYNC_SCRIPT")
[ -n "$log_fn" ] || fail 'log() definida en webcmp-deploy-sync.sh' "$log_fn" 'vacio'

set +e
LOG_FN="$log_fn" QUIET=1 bash -c 'set -Eeuo pipefail; eval "$LOG_FN"; log "silencioso"' \
    >/dev/null 2>&1
log_quiet_rc=$?
LOG_FN="$log_fn" QUIET=0 bash -c 'set -Eeuo pipefail; eval "$LOG_FN"; log "ruidoso"' \
    >/dev/null 2>&1
log_noisy_rc=$?
set -e
assert_eq 'log() con QUIET=1 no aborta bajo set -e' 0 "$log_quiet_rc"
assert_eq 'log() con QUIET=0 no aborta bajo set -e' 0 "$log_noisy_rc"

# --- --refresh crea refs/heads/main en el espejo ------------------------------

# Regresion: el fetch de --refresh era `git fetch origin refs/heads/main`, SIN
# refspec de destino. En un bare eso solo actualiza FETCH_HEAD: no crea ni mueve
# refs/heads/main. El timer 04:30 corre sin --refresh y sin --sha, asi que
# resolvia para siempre el SHA que hubiera en el espejo y re-instalaba los
# artefactos root de una version anterior.
refresh_state="$TEST_TMP/refresh-state"
mkdir -p "$refresh_state"
refresh_mirror="$refresh_state/webcmp-sync.mirror"
git init --bare "$refresh_mirror" >/dev/null 2>&1
git -C "$refresh_mirror" remote add origin "$REPO_ROOT" >/dev/null 2>&1
refresh_sha=$(git -C "$REPO_ROOT" rev-parse HEAD)
git -C "$refresh_mirror" fetch --quiet "$REPO_ROOT" "$refresh_sha" >/dev/null 2>&1
# A proposito SIN refs/heads/main: el setup del espejo real no lo trae (ver
# 192.168.122.240, donde hubo que crearlo a mano).

set +e
SYNC_STATE_DIR="$refresh_state" bash "$SYNC_SCRIPT" --quiet --refresh --sha "$refresh_sha" \
    >/dev/null 2>&1
refresh_rc=$?
set -e
# Sin root el helper muere en install: no es el fallo que se pina aca. Lo que
# importa es que el fetch de --refresh haya creado refs/heads/main en el espejo
# (el origen trae SU main; que sea o no el HEAD del checkout no es la regresion).
ref_after=$(git -C "$refresh_mirror" rev-parse refs/heads/main 2>/dev/null || true)
[ -n "$ref_after" ] \
    || fail '--refresh deja refs/heads/main en el espejo' \
        'refs/heads/main resolvible tras --refresh' 'refs/heads/main no existe'
ok '--refresh deja refs/heads/main en el espejo'

# El timer diario (webcmp-sync.service) corre SIN --sha: si no actualiza el
# espejo, resuelve el SHA viejo y re-instala artefactos root desactualizados.
assert_contains 'el timer de sync pasa --refresh' \
    'webcmp-deploy-sync.sh --quiet --refresh' \
    "$(cat "$REPO_ROOT/deploy/systemd/webcmp-sync.service")"

# El fetch de --refresh necesita refspec con destino: sin el ':destino' el fetch
# no crea ni mueve refs/heads/main en un bare (lo de arriba, visto en red).
assert_contains 'el fetch de --refresh usa refspec con destino' \
    '$BRANCH_REF:$BRANCH_REF' "$sync_src"
assert_contains 'install-deploy-sync.sh usa refspec con destino' \
    '$BRANCH_REF:$BRANCH_REF' "$(cat "$INSTALL_SYNC")"

# --- Sin espejo: falla cerrado ---------------------------------------------

set +e
no_mirror=$(bash "$SYNC_SCRIPT" --quiet 2>&1)
no_mirror_rc=$?
set -e
assert_eq 'webcmp-deploy-sync.sh sin espejo sale 1' 1 "$no_mirror_rc"
assert_contains 'webcmp-deploy-sync.sh sin espejo lo explica' \
    'Espejo root no existe' "$no_mirror"

# --- Con espejo: extrae del SHA, instala, escribe estado --------------------

setup_mirror
test_sha=$(git -C "$SYNC_MIRROR" rev-parse refs/heads/main)

# El manifest real apunta a /usr/local/sbin y /etc/systemd/system, donde un
# test no puede escribir. Se valida entonces que la extraccion del manifest
# y de cada archivo del SHA funciona: es lo unico que el sync puede hacer
# mal sin permisos.
for entry in $(awk '!/^#/ && NF { print $1 }' "$REPO_ROOT/deploy/root-bundle.manifest"); do
    set +e
    extracted=$(git -C "$SYNC_MIRROR" show "$test_sha:$entry" 2>&1)
    rc=$?
    set -e
    assert_eq "el SHA trae $entry" 0 "$rc"
    [ -n "$extracted" ] || fail "el SHA trae $entry" 'no vacio' "vacio"
done
ok "extraccion de todos los archivos del manifest: OK"

# --- Render de units --------------------------------------------------------

assert_contains 'sync define render_content' 'render_content()' "$sync_src"
assert_contains 'render sustituye /srv/webcmp' '/srv\/webcmp' "$sync_src"
assert_contains 'render sustituye User=webcmp' 'User=webcmp/User=' "$sync_src"
assert_contains 'render sustituye webcmp-huey' 'webcmp-huey/' "$sync_src"
# install.sh renderiza los .timer (Documentation=/srv/webcmp y Unit=). Si el
# sync no lo hace, instala un timer con el directorio equivocado en un server
# con otro APP_DIR y nadie lo nota.
assert_contains 'render cubre los .timer' 'systemd/*.timer' "$sync_src"

# --- Manifest: 4 campos por entrada -----------------------------------------

# El parser del helper exige EXACTAMENTE 4 campos (origen destino modo dueno).
# Regresion: el manifest se alinea con espacios pero el parser usaba
# IFS=$'\t', nunca dividia, src_path era la linea entera y el sync moria en la
# primera entrada (y en silencio, porque log() con --quiet ya habia matado el
# script antes).
assert_not_contains 'el parser no exige tabuladores' "IFS=\$'\\t'" "$sync_src"

manifest_entries=0
while IFS= read -r line; do
    [ -n "$line" ] || continue
    case "$line" in \#*) continue ;; esac
    read -r m_src m_dest m_mode m_owner m_extra <<< "$line"
    if [ -n "${m_extra:-}" ] || [ -z "${m_dest:-}" ] || [ -z "${m_mode:-}" ] || [ -z "${m_owner:-}" ]; then
        fail "manifest: 4 campos en '$line'" '4 campos' \
            "extra='${m_extra:-}' dest='${m_dest:-}' modo='${m_mode:-}' owner='${m_owner:-}'"
    else
        manifest_entries=$((manifest_entries + 1))
    fi
done < "$REPO_ROOT/deploy/root-bundle.manifest"
[ "$manifest_entries" -gt 0 ] || fail 'manifest con entradas' '> 0' '0'
ok "manifest: $manifest_entries entradas con 4 campos"

# --- Enganches ----------------------------------------------------------------

deploy_src=$(cat "$DEPLOY_SH")
assert_contains 'deploy.sh llama al sync con --refresh' \
    'webcmp-deploy-sync.sh --quiet --refresh --sha' "$deploy_src"
assert_contains 'deploy.sh: el sync es fail-open (no aborta)' \
    'fail-open; missing_units cubre el hueco' "$deploy_src"

install_src=$(cat "$INSTALL_SH")
assert_contains 'install.sh instala el sync (setup_deploy_sync)' \
    'setup_deploy_sync' "$install_src"

echo "Todos los tests de sync pasaron."

# run.sh sourcea los tests en un solo shell y no usa errexit: devolverlo a su
# estado original, o un test posterior que espere un fallo (el bloque root de
# test_install_apply_units.sh) abortaria la suite sin imprimir nada.
set +e
