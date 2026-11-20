# Pruebas de la pagina 50x que Nginx sirve mientras Gunicorn esta caido.
#
# Por que existe este archivo: el vhost versionado apunta `error_page 502 503 504`
# a `/50x.html` con `location = /50x.html { internal; root /var/www/webcmp-errors; }`.
# Si ese archivo no esta, Nginx devuelve un 404 DENTRO del manejo del error: el
# sintoma mas dificil de diagnosticar que existe.
#
# La pagina tiene que llegar al servidor por dos caminos, y los dos se prueban:
#   1. `install.sh` la escribe en una instalacion nueva.
#   2. `webcmp-deploy-sync.sh` la mantiene al dia en cada deploy (el boton
#      «Actualizar» corre deploy.sh -> sync, que instala lo que lista
#      deploy/root-bundle.manifest; install.sh NO se ejecuta en un deploy).

NGINX_ERROR_PAGE=$REPO_ROOT/deploy/nginx/50x.html
ERROR_PAGE_INSTALL=$REPO_ROOT/deploy/install.sh
ERROR_PAGE_MANIFEST=$REPO_ROOT/deploy/root-bundle.manifest
ERROR_PAGE_SYNC=$REPO_ROOT/deploy/webcmp-deploy-sync.sh

# ---------------------------------------------------------------------------
# La pagina versionada
# ---------------------------------------------------------------------------
#
# Es la unica fuente: install.sh la copia y el sync la instala desde el SHA. Si
# el contrato de la pagina se rompe (deja de reintentar, pierde el tema o la
# ilustracion), se rompe en los dos caminos a la vez.

assert_file 'la pagina 50x esta versionada en deploy/nginx' "$NGINX_ERROR_PAGE"

if [ -f "$NGINX_ERROR_PAGE" ]; then
    page_src=$(cat "$NGINX_ERROR_PAGE")
    assert_contains 'la pagina 50x reintenta sola' 'location.reload' "$page_src"
    assert_contains 'la pagina 50x respeta el tema del sitio' 'tabler-theme' "$page_src"
    assert_contains 'la pagina 50x acepta ?theme=' "get('theme')" "$page_src"
    assert_contains 'la pagina 50x usa la ilustracion de mantenimiento' \
        'maintenance.webp' "$page_src"
    assert_contains 'la pagina 50x muestra la imagen a 180px' 'height="180"' "$page_src"
    assert_contains 'la pagina 50x es HTML completo' '<!DOCTYPE html>' "$page_src"
    # El HTML va directo al servidor: un tag de plantilla o un placeholder sin
    # renderizar se sirve tal cual y nadie lo nota hasta que hay una caida.
    assert_not_contains 'la pagina 50x no tiene placeholders sin renderizar' \
        '{{' "$page_src"
fi

# ---------------------------------------------------------------------------
# install.sh: copia la versionada, no la embebe
# ---------------------------------------------------------------------------

if [ -f "$ERROR_PAGE_INSTALL" ]; then
    # Se extrae la funcion real del instalador: una copia en el test se
    # desactualiza sola.
    write_error_fn=$(awk '/^write_error_page\(\) \{/{f=1} f{print} f && /^}$/{exit}' "$ERROR_PAGE_INSTALL")

    if [ -n "$write_error_fn" ]; then
        assert_contains 'write_error_page toma la pagina versionada' \
            'deploy/nginx/50x.html' "$write_error_fn"
        assert_not_contains 'write_error_page ya no embebe el HTML' \
            '<!doctype html>' "$write_error_fn"
        # Idempotencia: reinstalar sin cambios no debe reescribir el archivo (ni
        # disparar un reload de Nginx de mas).
        assert_contains 'write_error_page instala solo si cambio' \
            'install_if_changed' "$write_error_fn"
    else
        fail 'write_error_page definida en install.sh' 'la funcion' 'no se encontro'
    fi
fi

# ---------------------------------------------------------------------------
# Manifest: el sync instala la pagina en cada deploy
# ---------------------------------------------------------------------------

if [ -f "$ERROR_PAGE_MANIFEST" ]; then
    manifest_src=$(cat "$ERROR_PAGE_MANIFEST")
    assert_contains 'el manifest incluye la pagina 50x' \
        'deploy/nginx/50x.html' "$manifest_src"
    assert_contains 'la pagina 50x se instala en /var/www/webcmp-errors' \
        '/var/www/webcmp-errors/50x.html' "$manifest_src"

    # La linea tiene que tener los 4 campos exactos del parser del sync y el
    # dueno/modo que espera Nginx: root-owned 0644, servible por www-data.
    page_line=$(awk '$1 == "deploy/nginx/50x.html" { print; exit }' "$ERROR_PAGE_MANIFEST")
    read -r p_src p_dest p_mode p_owner p_extra <<< "${page_line:-}"
    assert_eq 'pagina 50x: destino del manifest' \
        '/var/www/webcmp-errors/50x.html' "${p_dest:-}"
    assert_eq 'pagina 50x: modo del manifest' '0644' "${p_mode:-}"
    assert_eq 'pagina 50x: dueno del manifest' 'root:root' "${p_owner:-}"
    assert_eq 'pagina 50x: sin campo de mas' '' "${p_extra:-}"
fi

# ---------------------------------------------------------------------------
# Sync: crea el directorio destino si falta
# ---------------------------------------------------------------------------
#
# `/var/www/webcmp-errors` lo crea install.sh. En un servidor que ya estaba
# instalado, el primer deploy que traiga la pagina corre el sync contra un
# directorio que no existe: `install` no crea padres y el sync moriria con un
# error que no dice nada del 50x.

if [ -f "$ERROR_PAGE_SYNC" ]; then
    sync_page_src=$(cat "$ERROR_PAGE_SYNC")
    # Se afirma sobre un booleano, no sobre el script entero: un fallo que
    # imprime 200 lineas de sync esconde el resto de la corrida.
    has_ensure_def=no
    has_ensure_call=no
    has_install_d=no
    case "$sync_page_src" in *'ensure_dest_dir() {'*) has_ensure_def=si ;; esac
    case "$sync_page_src" in *'ensure_dest_dir "$dest_path"'*) has_ensure_call=si ;; esac
    case "$sync_page_src" in *'install -d'*) has_install_d=si ;; esac

    assert_eq 'el sync define la creacion del directorio destino' 'si' "$has_ensure_def"
    assert_eq 'el sync llama a ensure_dest_dir antes de instalar' 'si' "$has_ensure_call"
    assert_eq 'el sync crea el directorio con install -d' 'si' "$has_install_d"
fi

# ---------------------------------------------------------------------------
# Vhosts: siguen apuntando a la pagina
# ---------------------------------------------------------------------------

for vhost in "$REPO_ROOT"/deploy/nginx/webcmp.conf.example \
             "$REPO_ROOT"/deploy/nginx/webcmp-http.conf.example; do
    [ -f "$vhost" ] || continue
    vhost_src=$(cat "$vhost")
    assert_contains "$(basename "$vhost") declara error_page 502/503/504" \
        'error_page 502 503 504 /50x.html;' "$vhost_src"
    assert_contains "$(basename "$vhost") sirve /50x.html desde el root de errores" \
        'root /var/www/webcmp-errors;' "$vhost_src"
done
