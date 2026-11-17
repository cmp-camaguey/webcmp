# Log del ejecutor del boton "Actualizar" (change 037-log-del-despliegue).
#
# Lo que importa probar:
#
#   1. La salida del deploy llega AL ARCHIVO, no solo al journal: el panel no
#      lee el journal y este archivo es lo que queda visible cuando nadie
#      tiene SSH al servidor.
#   2. El archivo queda legible para el proceso web (0644).
#   3. Nadie rota este archivo: lo rota el propio ejecutor antes de cada
#      corrida, y el recorte conserva lo ultimo.
#   4. Un log que no se puede escribir NO tumba un deploy que salio bien.
#   5. El codigo de salida sigue siendo el del deploy, no el de `tee`.
#
# Corre el script completo contra un repo git local y un `sudo` de mentira: en
# esa configuracion no pide red, ni privilegios, ni el sistema del operador.
#
# Se ejecuta con `source` desde run.sh; no se corre solo.

AUTODEPLOY_SH=$REPO_ROOT/deploy/autodeploy.sh

ad_dir=$(mktemp -d)

# Repo remoto local: el ejecutor resuelve `refs/heads/main` con `git ls-remote`
# y no hay otra forma de enterarse de que hay un deploy que pedir.
git init --quiet -b main --bare "$ad_dir/remote.git"
git init --quiet -b main "$ad_dir/work"
git -C "$ad_dir/work" -c user.email=test@example.com -c user.name=test \
    commit --quiet --allow-empty -m init
git -C "$ad_dir/work" remote add origin "$ad_dir/remote.git"
git -C "$ad_dir/work" push --quiet origin main

# `sudo -n <comando>`: el stub descarta el `-n` y ejecuta el resto. Sin esto
# el test dependeria de que la cuenta que lo corre pueda hacer sudo.
mkdir -p "$ad_dir/bin"
printf '#!/usr/bin/env bash\nshift\nexec "$@"\n' >"$ad_dir/bin/sudo"
chmod +x "$ad_dir/bin/sudo"

# El deploy de mentira. Imprime en stdout Y en stderr, que es por donde sale
# todo lo que el panel necesita ver, y sale con el codigo que el test pida.
cat >"$ad_dir/deploy-stub" <<'AD_STUB'
#!/usr/bin/env bash
echo "==> paso de prueba"
echo "ERROR simulado: el motivo del fallo" >&2
exit "${STUB_RC:-0}"
AD_STUB
chmod +x "$ad_dir/deploy-stub"

# ad_run <rc> [VAR=valor ...]
#
# Corre el ejecutor entero. Las variables extra van como pares al final, antes
# del comando, que es lo que `env` acepta.
ad_run() {
    local rc=$1
    shift
    env \
        PATH="$ad_dir/bin:$PATH" \
        STATUS_FILE="$ad_dir/deploy-status.json" \
        PROGRESS_FILE="$ad_dir/deploy-progress.json" \
        REQUEST_FILE="$ad_dir/deploy-request" \
        LOCKFILE="$ad_dir/autodeploy.lock" \
        DEPLOY_LOG="$ad_dir/deploy.log" \
        DEPLOY_SCRIPT="$ad_dir/deploy-stub" \
        REPO_URL="$ad_dir/remote.git" \
        BRANCH_REF=refs/heads/main \
        STUB_RC="$rc" \
        "$@" \
        bash "$AUTODEPLOY_SH"
}

ad_log() { cat "$ad_dir/deploy.log" 2>/dev/null; }

# --- Camino feliz: el log lleva la salida del deploy ------------------------

ad_out=$(ad_run 0 2>&1)
ad_rc=$?
assert_eq 'autodeploy: el camino feliz sale 0' 0 "$ad_rc"
assert_contains 'autodeploy: el log lleva el stdout del deploy' \
    '==> paso de prueba' "$(ad_log)"
assert_contains 'autodeploy: el log lleva el stderr del deploy' \
    'ERROR simulado: el motivo del fallo' "$(ad_log)"
assert_contains 'autodeploy: el log lleva el desenlace' \
    'Despliegue OK' "$(ad_log)"
assert_contains 'autodeploy: el log lleva lo que escribe el propio ejecutor' \
    'autodeploy: Desplegando' "$(ad_log)"
assert_contains 'autodeploy: el journal sigue recibiendo lo mismo' \
    '==> paso de prueba' "$ad_out"
assert_contains 'autodeploy: el estado queda en ok' \
    '"status": "ok"' "$(cat "$ad_dir/deploy-status.json" 2>/dev/null)"

ad_mode=$(stat -c '%a' "$ad_dir/deploy.log" 2>/dev/null || printf '?')
assert_eq 'autodeploy: el log queda legible para el proceso web' 644 "$ad_mode"

# --- Fallo: el motivo queda en el archivo, no solo en el journal ------------

ad_out=$(ad_run 1 2>&1)
ad_rc=$?
assert_eq 'autodeploy: un deploy fallido sale con 1' 1 "$ad_rc"
assert_contains 'autodeploy: el log guarda el motivo del fallo' \
    'ERROR simulado: el motivo del fallo' "$(ad_log)"
assert_contains 'autodeploy: el log guarda que fallo' \
    'El despliegue fallo' "$(ad_log)"
assert_contains 'autodeploy: el estado queda en failed' \
    '"status": "failed"' "$(cat "$ad_dir/deploy-status.json" 2>/dev/null)"
assert_contains 'autodeploy: el aviso apunta al log del panel' \
    'Ver el log en el panel' "$ad_out"

# --- Recorte: nadie lo rota, el propio ejecutor si --------------------------

# Se rellena con mas de 6x el tope. El recorte conserva la COLA, asi que lo
# que tiene que desaparecer es el volumen viejo, no la ultima linea: despues
# de conservar la mitad del tope quedan unas pocas lineas de relleno, no 400.
: >"$ad_dir/deploy.log"
for ad_i in $(seq 1 400); do
    printf 'linea vieja %04d - relleno para pasar el tope de recorte\n' "$ad_i" \
        >>"$ad_dir/deploy.log"
done

ad_run 0 DEPLOY_LOG_MAX_BYTES=2048 >/dev/null 2>&1
ad_size=$(wc -c <"$ad_dir/deploy.log" | tr -d ' ')
ad_old_lines=$(grep -c 'linea vieja' "$ad_dir/deploy.log" || true)

# La mitad del tope (1024) mas lo que agrega esta corrida. El tope no es una
# cota exacta del archivo final: es lo que se conserva ANTES de escribir.
if [ "$ad_size" -le 4096 ]; then
    ok 'autodeploy: el log no crece sin techo'
else
    fail 'autodeploy: el log no crece sin techo' 'menos de 4096 bytes' "$ad_size"
fi
if [ "$ad_old_lines" -lt 40 ]; then
    ok 'autodeploy: el recorte se lleva lo viejo'
else
    fail 'autodeploy: el recorte se lleva lo viejo' \
        'menos de 40 lineas de relleno' "$ad_old_lines"
fi
assert_contains 'autodeploy: el recorte conserva lo ultimo' \
    'Despliegue OK' "$(ad_log)"

# --- Un log que no se puede escribir no tumba el deploy ---------------------
# El directorio no existe: ni `tee` ni el ejecutor pueden crear el archivo.
# Un disco lleno o un permiso borrado no pueden convertir un deploy que salio
# bien en un fallo, ni tapar el estado del panel.

ad_out=$(ad_run 0 DEPLOY_LOG="$ad_dir/no-existe/deploy.log" 2>&1)
ad_rc=$?
assert_eq 'autodeploy: un log inescribible no tumba el deploy' 0 "$ad_rc"
assert_contains 'autodeploy: el estado sigue quedando en ok' \
    '"status": "ok"' "$(cat "$ad_dir/deploy-status.json" 2>/dev/null)"
assert_contains 'autodeploy: la salida igual llega al journal' \
    '==> paso de prueba' "$ad_out"
