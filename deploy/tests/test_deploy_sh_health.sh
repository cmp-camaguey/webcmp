#!/usr/bin/env bash
# Pruebas de la decision del health check (deploy/deploy.sh).
#
# Se ejercita la funcion real, extraida del script entre los marcadores
# TEST-BLOCK, no una copia que puede quedar desactualizada.
#
# Lo que importa no es el formato del mensaje sino el contrato: un 2xx o 3xx
# pasa; un 503 que el modo de mantenimiento explica (con la ruta exenta
# atendiendo) pasa y lo dice; cualquier otra cosa aborta, incluido el caso en
# que no se puede confirmar que el 503 venga del mantenimiento. Ese ultimo es
# el lado cerrado: sin evidencia de que sea una ventana anunciada, un 503 sigue
# siendo una caida.
#
# Se ejecuta con `source` desde run.sh; no se corre solo.

DEPLOY_SH=$REPO_ROOT/deploy/deploy.sh

verdict_body=$(require_block health-verdict "$DEPLOY_SH")

# run_verdict <codigo> <mantenimiento yes|no> <codigo-de-login>
#
# Corre la funcion real en un subshell con los globals que el script define en
# el arranque y con las tres dependencias externas reemplazadas: `manage` (la
# pregunta al flag), el probe de /login/ y la salida.
run_verdict() {
    local code=$1 maintenance=$2 login_code=$3
    (
        eval "$verdict_body"
        GUNICORN_UNIT=webcmp
        CONFIG=/etc/webcmp/deploy.env
        HEALTHCHECK_UNIX_SOCKET=
        HEALTHCHECK_INSECURE=
        hc_url='http://www.example.test/'
        hc_args=()
        log() { printf 'LOG %s\n' "$*"; }
        die() { printf 'ERROR %s\n' "$*" >&2; exit 1; }
        site_in_maintenance() { [ "$maintenance" = yes ]; }
        health_probe_login() { printf '%s' "$login_code"; }
        health_verdict "$code"
    )
}

# --- 2xx y 3xx pasan sin tocar nada mas ------------------------------------

out=$(run_verdict 200 yes 200)
rc=$?
assert_eq 'health: 200 sale 0' 0 "$rc"
assert_contains 'health: 200 informa el codigo' 'El sitio responde 200' "$out"

out=$(run_verdict 302 no 302)
rc=$?
assert_eq 'health: 302 sale 0' 0 "$rc"

# --- 503 con el modo de mantenimiento encendido ----------------------------
#
# Es el caso del deploy de v0.7.2: la ventana de mantenimiento abierta hacia
# que la pagina publica contestara 503 y el deploy sano revirtiera solo.

out=$(run_verdict 503 yes 200)
rc=$?
assert_eq 'health: 503 con mantenimiento y /login/ arriba sale 0' 0 "$rc"
assert_contains 'health: avisa que el 503 es el modo de mantenimiento' \
    'modo de mantenimiento encendido' "$out"
assert_contains 'health: aclara que la pagina publica no se verifica' \
    'pagina publica no se verifica' "$out"
assert_contains 'health: informa el codigo de la ruta exenta' \
    '/login/ responde 200' "$out"

# --- 503 con el mantenimiento apagado --------------------------------------

out=$(run_verdict 503 no 200 2>&1)
rc=$?
assert_eq 'health: 503 sin mantenimiento aborta' 1 "$rc"
assert_contains 'health: 503 sin mantenimiento lo explica' \
    'el modo de mantenimiento no lo explica' "$out"

# --- 503 con el mantenimiento encendido pero la aplicacion caida ----------
#
# El flag encendido no es un pase libre: si la ruta exenta tampoco atiende, no
# es una ventana de mantenimiento, es un deploy roto.

out=$(run_verdict 503 yes 000 2>&1)
rc=$?
assert_eq 'health: mantenimiento encendido con /login/ sin respuesta aborta' 1 "$rc"
assert_contains 'health: nombra el codigo de la ruta exenta' \
    '/login/ responde 000' "$out"

out=$(run_verdict 503 yes 500 2>&1)
rc=$?
assert_eq 'health: mantenimiento encendido con /login/ en 500 aborta' 1 "$rc"

# --- El resto de los codigos sigue fallando como antes ---------------------

out=$(run_verdict 000 no 200 2>&1)
rc=$?
assert_eq 'health: 000 aborta' 1 "$rc"
assert_contains 'health: 000 nombra el destino' 'Sin respuesta de http://www.example.test/' "$out"

out=$(run_verdict 404 no 200 2>&1)
rc=$?
assert_eq 'health: 404 aborta' 1 "$rc"
assert_contains 'health: 404 pide 2xx o 3xx' 'se esperaba 2xx o 3xx' "$out"

# --- La ruta exenta se arma con el mismo transporte ------------------------

probe_url=$(mktemp "${TMPDIR:-/tmp}/webcmp-hc.XXXXXX")
out=$(
    eval "$verdict_body"
    hc_url='http://www.example.test/'
    hc_args=(--silent --resolve 'www.example.test:80:127.0.0.1')
    curl() {
        printf '%s' "$*" >"$probe_url"
        printf '200'
    }
    health_probe_login
)
assert_eq 'health: el probe de /login/ devuelve el codigo del curl' '200' "$out"
assert_contains 'health: el probe va a la ruta exenta' \
    'http://www.example.test/login/' "$(cat "$probe_url")"
assert_contains 'health: el probe reutiliza el --resolve del health check' \
    '--resolve www.example.test:80:127.0.0.1' "$(cat "$probe_url")"
rm -f "$probe_url"

# --- La pregunta al flag tolera el ruido de manage.py ----------------------
#
# `manage shell -c` imprime la linea de importacion automatica antes del
# resultado: el `grep -qx True` tiene que quedarse con la ultima linea y no
# con cualquier "True" colgado de un traceback.

flag_probe() {
    local salida=$1
    (
        eval "$verdict_body"
        manage() { printf '%s\n' "$salida"; }
        site_in_maintenance
    )
}

flag_probe 'True' >/dev/null 2>&1
assert_eq 'health: flag en True se lee como encendido' 0 $?

flag_probe '41 objects imported automatically (use -v 2 for details).
True' >/dev/null 2>&1
assert_eq 'health: el ruido de manage.py no tapa el resultado' 0 $?

flag_probe 'False' >/dev/null 2>&1
assert_eq 'health: flag en False se lee como apagado' 1 $?

flag_probe '' >/dev/null 2>&1
assert_eq 'health: sin salida no se confirma el mantenimiento' 1 $?

flag_probe 'SomeError: True' >/dev/null 2>&1
assert_eq 'health: un True suelto en un error no confirma el mantenimiento' 1 $?
