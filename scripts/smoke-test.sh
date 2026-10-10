#!/usr/bin/env bash
# Start an image the way production would, wait for it to become healthy, and probe it.
#
# Usage:   scripts/smoke-test.sh IMAGE
# Env:     SMOKE_TIMEOUT   seconds to wait for "healthy" (default 40)
#          SMOKE_ENV       extra "-e KEY=VALUE" pairs, space separated (used to test broken configs)
# Exit:    0 = healthy and all probes passed, 1 = failure (container logs are printed)
set -euo pipefail

image=${1:?usage: smoke-test.sh IMAGE}
timeout=${SMOKE_TIMEOUT:-40}
name="smoke-$$-$RANDOM"

log() { printf '[smoke] %s\n' "$*"; }
fail() {
  log "FAIL: $*"
  log "container state: $(docker inspect -f '{{.State.Status}} exit={{.State.ExitCode}} health={{if .State.Health}}{{.State.Health.Status}}{{end}}' "$name" 2>/dev/null || echo unknown)"
  log "last container logs:"
  docker logs --tail 30 "$name" 2>&1 | sed 's/^/    /' || true
  exit 1
}
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

env_args=()
for pair in ${SMOKE_ENV:-}; do env_args+=(-e "$pair"); done

log "starting $image as $name"
docker run -d --name "$name" \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 256m --cpus 0.5 \
  -p 127.0.0.1::8000 "${env_args[@]}" "$image" >/dev/null

deadline=$((SECONDS + timeout))
while :; do
  status=$(docker inspect -f '{{.State.Status}}' "$name")
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name")
  [[ $status == running && $health == healthy ]] && break
  [[ $status == exited || $status == dead ]] && fail "container stopped during startup"
  [[ $health == unhealthy ]] && fail "Docker HEALTHCHECK reports unhealthy"
  ((SECONDS < deadline)) || fail "not healthy after ${timeout}s (status=$status health=$health)"
  sleep 1
done
port=$(docker port "$name" 8000/tcp | head -1 | cut -d: -f2)
base="http://127.0.0.1:$port"
log "healthy; probing $base"

expect_status() {  # path expected_code
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$base$1") || code=000
  [[ $code == "$2" ]] || fail "GET $1 returned $code, expected $2"
  log "GET $1 -> $code"
}
expect_status /health 200
expect_status /ready 200
expect_status /api/v1/primes/10 200
expect_status /api/v1/primes/-1 422

body=$(curl -s --max-time 5 "$base/api/v1/primes/10")
[[ $body == *'"prime_count":4'* ]] || fail "unexpected primes response: $body"
curl -s --max-time 5 "$base/metrics" | grep -q '^http_requests_total{' || fail "/metrics has no http_requests_total"
log "metrics exposed"

uid=$(docker exec "$name" id -u)
[[ $uid != 0 ]] || fail "container is running as root"
log "running as uid $uid (non-root)"
log "PASS"
