#!/usr/bin/env bash
# Regenerate fully pinned requirement files (direct + transitive) in a clean venv.
# Usage: scripts/lock-deps.sh   (run from the repository root on Linux/WSL)
set -euo pipefail

cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

python3 -m venv "$tmp/runtime"
"$tmp/runtime/bin/pip" install --quiet --upgrade pip
"$tmp/runtime/bin/pip" install --quiet fastapi uvicorn prometheus-client
{
  echo "# Runtime dependencies (fully pinned). Regenerate with scripts/lock-deps.sh"
  "$tmp/runtime/bin/pip" freeze --exclude pip
} > requirements.txt

python3 -m venv "$tmp/dev"
"$tmp/dev/bin/pip" install --quiet --upgrade pip
"$tmp/dev/bin/pip" install --quiet -r requirements.txt pytest pytest-cov httpx2 ruff pip-audit pyyaml
{
  echo "# Development/CI tools (fully pinned). Regenerate with scripts/lock-deps.sh"
  echo "-r requirements.txt"
  "$tmp/dev/bin/pip" freeze --exclude pip | grep -v -x -F -f <(grep -v '^#' requirements.txt)
} > requirements-dev.txt

echo "Locked: $(grep -vc '^#' requirements.txt) runtime, $(grep -vc -e '^#' -e '^-r' requirements-dev.txt) dev packages"
