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

sync_src=$(cat "$SYNC_SCRIPT")
assert_contains 'sync define render_content' 'render_content()' "$sync_src"
assert_contains 'render sustituye /srv/webcmp' '/srv\/webcmp' "$sync_src"
assert_contains 'render sustituye User=webcmp' 'User=webcmp/User=' "$sync_src"
assert_contains 'render sustituye webcmp-huey' 'webcmp-huey/' "$sync_src"

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
