#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/susnet-next/services/joe-cabot-lite"
DEST_DIR="/home/codex/joe-cabot-lite"
REV="$(git -C "$REPO_ROOT" rev-parse --short HEAD || echo unknown)"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -f "$SRC_DIR/joe_cabot_lite.py" ]]; then
  echo "source missing at $SRC_DIR" >&2
  exit 1
fi

sudo install -d -o codex -g codex "$DEST_DIR"

if command -v rsync >/dev/null 2>&1; then
  sudo rsync -a --delete --chown=codex:codex \
    "$SRC_DIR/" "$DEST_DIR/" \
    --exclude '.venv' \
    --exclude '__pycache__'
else
  sudo -u codex rm -f "$DEST_DIR/joe_cabot_lite.py" "$DEST_DIR/ask_joe.py" "$DEST_DIR/requirements.txt" "$DEST_DIR/Dockerfile" "$DEST_DIR/docker-compose.yml" "$DEST_DIR/README.md"
  sudo cp "$SRC_DIR/joe_cabot_lite.py" "$DEST_DIR/joe_cabot_lite.py"
  sudo cp "$SRC_DIR/ask_joe.py" "$DEST_DIR/ask_joe.py"
  sudo cp "$SRC_DIR/requirements.txt" "$DEST_DIR/requirements.txt"
  sudo cp "$SRC_DIR/Dockerfile" "$DEST_DIR/Dockerfile"
  sudo cp "$SRC_DIR/docker-compose.yml" "$DEST_DIR/docker-compose.yml"
  sudo cp "$SRC_DIR/README.md" "$DEST_DIR/README.md"
  sudo chown codex:codex "$DEST_DIR/joe_cabot_lite.py" "$DEST_DIR/ask_joe.py" "$DEST_DIR/requirements.txt" "$DEST_DIR/Dockerfile" "$DEST_DIR/docker-compose.yml" "$DEST_DIR/README.md"
fi

sudo chmod +x "$DEST_DIR/ask_joe.py"

sudo -u codex /usr/bin/python3 -m venv "$DEST_DIR/.venv"
sudo -u codex "$DEST_DIR/.venv/bin/pip" install --quiet --disable-pip-version-check -r "$DEST_DIR/requirements.txt"
sudo -u codex "$DEST_DIR/.venv/bin/python" -m py_compile "$DEST_DIR/joe_cabot_lite.py" "$DEST_DIR/ask_joe.py"

printf 'repo=%s\nrev=%s\ndeployed_utc=%s\n' "susnet" "$REV" "$STAMP" | sudo tee "$DEST_DIR/DEPLOYED_FROM_REPO" >/dev/null
sudo chown codex:codex "$DEST_DIR/DEPLOYED_FROM_REPO"

sudo systemctl restart joe-cabot-lite
sleep 1
systemctl is-active joe-cabot-lite >/dev/null

echo "deployed $REV at $STAMP"
