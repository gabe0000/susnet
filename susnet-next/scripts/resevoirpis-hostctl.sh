#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$HOME/susnet-next"
OPS_DIR="$REPO_ROOT/ops/resevoir-stack"
STATE_ROOT="$HOME/resevoirpis-state-bundles"
STATE_MARKER="$HOME/.resevoirpis/active-state.json"
MANAGED_FILE="$OPS_DIR/shutdown-targets.txt"
PROTECTED_FILE="$OPS_DIR/protected-services.txt"
ALLOWLIST_FILE="$OPS_DIR/file-allowlist.txt"
FLASH_SCRIPT=""

mkdir -p "$OPS_DIR" "$STATE_ROOT" "$(dirname "$STATE_MARKER")"

DOCKER_BIN=()
if docker info >/dev/null 2>&1; then
  DOCKER_BIN=(docker)
elif sudo -n docker info >/dev/null 2>&1; then
  DOCKER_BIN=(sudo -n docker)
else
  echo "docker access unavailable" >&2
  exit 2
fi

docker_cmd() {
  "${DOCKER_BIN[@]}" "$@"
}

read_list() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  grep -Ev '^\s*#|^\s*$' "$file" || true
}

service_status() {
  local svc="$1"
  if [[ "$svc" == "tailscaled" ]]; then
    systemctl is-active tailscaled 2>/dev/null || echo "inactive"
    return 0
  fi
  local st
  st="$(docker_cmd inspect -f '{{.State.Status}}' "$svc" 2>/dev/null || true)"
  if [[ -z "$st" ]]; then
    echo "missing"
  else
    echo "$st"
  fi
}

infer_active() {
  local running=0
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    if [[ "$(service_status "$svc")" == "running" ]]; then
      running=1
      break
    fi
  done < <(read_list "$MANAGED_FILE")

  if [[ "$running" -eq 1 ]]; then
    echo "resevoir"
  else
    echo "normal"
  fi
}

get_active() {
  if [[ -f "$STATE_MARKER" ]]; then
    python3 - "$STATE_MARKER" <<'PY'
import json,sys
try:
    print(json.load(open(sys.argv[1], encoding='utf-8')).get('active_state','normal'))
except Exception:
    print('normal')
PY
  else
    infer_active
  fi
}

set_active() {
  local state="$1"
  python3 - "$STATE_MARKER" "$state" <<'PY'
import json,sys,datetime,os
path,state=sys.argv[1],sys.argv[2]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path,'w',encoding='utf-8') as f:
    json.dump({'active_state':state,'updated_ts':datetime.datetime.utcnow().isoformat()+'Z'},f,indent=2)
print(path)
PY
}

preflight() {
  if [[ "$(systemctl is-active tailscaled 2>/dev/null || true)" != "active" ]]; then
    echo "tailscaled is not active" >&2
    return 1
  fi
  docker_cmd ps >/dev/null
}

assert_no_overlap() {
  local overlap
  overlap="$(comm -12 <(read_list "$MANAGED_FILE" | sort -u) <(read_list "$PROTECTED_FILE" | sort -u) || true)"
  if [[ -n "$overlap" ]]; then
    echo "managed/protected overlap detected:" >&2
    echo "$overlap" >&2
    return 1
  fi
}

managed_services() { read_list "$MANAGED_FILE" | tr '\n' ' '; }
protected_services() { read_list "$PROTECTED_FILE" | tr '\n' ' '; }

managed_status() {
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    echo "$svc=$(service_status "$svc")"
  done < <(read_list "$MANAGED_FILE")
}

protected_status() {
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    echo "$svc=$(service_status "$svc")"
  done < <(read_list "$PROTECTED_FILE")
}

status_table() {
  echo "MANAGED"
  managed_status
  echo "PROTECTED"
  protected_status
}

stop_managed() {
  assert_no_overlap
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    local st
    st="$(service_status "$svc")"
    if [[ "$st" == "running" ]]; then
      docker_cmd stop "$svc" >/dev/null
    fi
  done < <(read_list "$MANAGED_FILE")
}

start_managed() {
  assert_no_overlap
  local failed=0
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    local st
    st="$(service_status "$svc")"
    if [[ "$st" == "missing" ]]; then
      echo "managed service missing: $svc" >&2
      failed=1
      continue
    fi
    if [[ "$st" != "running" ]]; then
      if ! docker_cmd start "$svc" >/dev/null; then
        echo "failed to start $svc" >&2
        failed=1
      fi
    fi
  done < <(read_list "$MANAGED_FILE")
  [[ "$failed" -eq 0 ]]
}

verify_managed_running() {
  local failed=0
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    if [[ "$(service_status "$svc")" != "running" ]]; then
      echo "managed service not running: $svc" >&2
      failed=1
    fi
  done < <(read_list "$MANAGED_FILE")
  [[ "$failed" -eq 0 ]]
}

snapshot_state() {
  local state="$1"
  local context="$2"
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  local bundle="$STATE_ROOT/$state/$ts"
  mkdir -p "$bundle/volumes"

  managed_status > "$bundle/managed-status.txt"
  protected_status > "$bundle/protected-status.txt"

  local git_sha="unknown"
  if [[ -d "$REPO_ROOT/.git" ]]; then
    git_sha="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
  fi

  python3 - "$bundle/manifest.json" "$state" "$context" "$git_sha" <<'PY'
import json,sys,datetime,socket
path,state,context,sha=sys.argv[1:5]
with open(path,'w',encoding='utf-8') as f:
    json.dump({
      'host':socket.gethostname(),
      'state':state,
      'context':context,
      'captured_ts':datetime.datetime.utcnow().isoformat()+'Z',
      'repo_sha':sha,
      'format_version':1
    },f,indent=2)
PY

  local paths=()
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    local expanded
    expanded="${item/#\~/$HOME}"
    if [[ -e "$expanded" ]]; then
      paths+=("$expanded")
    fi
  done < <(read_list "$ALLOWLIST_FILE")

  if [[ "${#paths[@]}" -gt 0 ]]; then
    tar --absolute-names -czf "$bundle/files.tar.gz" "${paths[@]}"
  fi

  : > "$bundle/volumes.txt"
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    docker_cmd inspect "$svc" --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' 2>/dev/null || true
  done < <(read_list "$MANAGED_FILE") | sed '/^$/d' | sort -u > "$bundle/volumes.txt"

  while IFS= read -r vol; do
    [[ -z "$vol" ]] && continue
    docker_cmd run --rm -v "$vol:/from:ro" -v "$bundle/volumes:/to" busybox sh -c "cd /from && tar czf /to/${vol}.tgz ."
  done < "$bundle/volumes.txt"

  (
    cd "$bundle"
    find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt
  )

  echo "$bundle"
}

resolve_latest_bundle() {
  local state="$1"
  local dir="$STATE_ROOT/$state"
  if [[ ! -d "$dir" ]]; then
    return 3
  fi
  local latest
  latest="$(ls -1dt "$dir"/* 2>/dev/null | head -n1 || true)"
  if [[ -z "$latest" ]]; then
    return 3
  fi
  echo "$latest"
}

restore_bundle() {
  local bundle="$1"
  [[ -d "$bundle" ]] || { echo "bundle not found: $bundle" >&2; return 1; }
  if [[ -f "$bundle/SHA256SUMS.txt" ]]; then
    (cd "$bundle" && sha256sum -c SHA256SUMS.txt >/dev/null)
  fi

  if [[ -f "$bundle/files.tar.gz" ]]; then
    tar -xzf "$bundle/files.tar.gz" -C /
  fi

  if [[ -f "$bundle/volumes.txt" ]]; then
    while IFS= read -r vol; do
      [[ -z "$vol" ]] && continue
      [[ -f "$bundle/volumes/${vol}.tgz" ]] || continue
      docker_cmd volume rm -f "$vol" >/dev/null 2>&1 || true
      docker_cmd volume create "$vol" >/dev/null
      docker_cmd run --rm -v "$vol:/to" -v "$bundle/volumes:/from:ro" busybox sh -c "cd /to && tar xzf /from/${vol}.tgz"
    done < "$bundle/volumes.txt"
  fi
  echo "$bundle"
}

restore_latest() {
  local state="$1"
  local bundle
  if ! bundle="$(resolve_latest_bundle "$state")"; then
    return 3
  fi
  restore_bundle "$bundle"
}

flash_rak() {
  echo "flash-rak not configured for this host" >&2
  return 64
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  preflight) preflight ;;
  managed-services) managed_services ;;
  protected-services) protected_services ;;
  managed-status) managed_status ;;
  protected-status) protected_status ;;
  status-table) status_table ;;
  stop-managed) stop_managed ;;
  start-managed) start_managed ;;
  verify-managed-running) verify_managed_running ;;
  snapshot) snapshot_state "${1:?state required}" "${2:-manual}" ;;
  restore-latest) restore_latest "${1:?state required}" ;;
  restore-path) restore_bundle "${1:?bundle path required}" ;;
  get-active) get_active ;;
  set-active) set_active "${1:?state required}" ;;
  flash-rak) flash_rak ;;
  help|*)
    echo "commands: preflight managed-services protected-services managed-status protected-status status-table stop-managed start-managed verify-managed-running snapshot restore-latest restore-path get-active set-active flash-rak"
    ;;
esac
