#!/bin/bash
# Worker de respaldo/restauración para DESARROLLO. En producción lo hacen las
# unidades systemd webcmp-backup.path / webcmp-restore.path, que disparan
# webcmp-deploy como root.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "No encuentro $PYTHON." >&2
  echo "El venv no está instalado. Corré 'make setup'." >&2
  exit 1
fi

cd "$REPO_DIR"
exec "$PYTHON" manage.py db_backup_worker --watch
