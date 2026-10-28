#!/usr/bin/env bash
# Export this repository read-only to the local minikube cluster.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
git -C "$root" rev-parse --verify main >/dev/null
mkdir -p "$root/.local"
pid_file="$root/.local/git-daemon.pid"
if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
  echo "Local Git source already running (PID $(cat "$pid_file"))."
  exit 0
fi
git daemon --detach --reuseaddr --listen=127.0.0.1 --port=19418 \
  --pid-file="$pid_file" --base-path="$(dirname "$root")" \
  --export-all --strict-paths "$root/.git"
echo "Read-only Git source started on localhost:19418. Only committed changes are served."
