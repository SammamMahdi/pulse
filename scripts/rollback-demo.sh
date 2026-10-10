#!/usr/bin/env bash
# Local deploy + rollback with Docker Compose using immutable, prebuilt image tags.
# Rollback = redeploy the previous known-good tag; nothing is rebuilt.
#
# Usage: scripts/rollback-demo.sh GOOD_TAG NEW_TAG     (both pulse-api:<tag> images must exist)
set -euo pipefail

good=${1:?usage: rollback-demo.sh GOOD_TAG NEW_TAG}
new=${2:?usage: rollback-demo.sh GOOD_TAG NEW_TAG}
port=${HOST_PORT:-8000}
export HOST_PORT=$port
cd "$(dirname "$0")/.."

deploy() {
  echo "--- deploying pulse-api:$1"
  TAG=$1 docker compose up -d --no-build --wait --wait-timeout 60
  docker compose ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'
  echo "running version: $(curl -s --max-time 5 "http://127.0.0.1:$port/api/v1/info" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
}

trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
deploy "$good"
deploy "$new"
echo "--- simulated bad release detected; rolling back to $good"
deploy "$good"
curl -sf --max-time 5 "http://127.0.0.1:$port/ready" >/dev/null && echo "readiness after rollback: OK"
