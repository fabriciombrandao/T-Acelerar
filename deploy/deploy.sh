#!/usr/bin/env bash
# Deploy/atualização em VPS sem Docker.
# Uso: ./deploy/deploy.sh   (rodar de dentro de /opt/winthor-data-deploy)
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

echo "==> git pull"
git pull --ff-only

echo "==> venv + dependências"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "==> testes (não faz deploy se quebrar)"
PYTHONPATH=backend python3 -m pytest backend/tests/ -q

echo "==> reiniciando serviço"
sudo systemctl restart winthor-data-deploy
sudo systemctl status winthor-data-deploy --no-pager -l | head -15

echo "==> OK"
