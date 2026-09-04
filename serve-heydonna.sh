#!/usr/bin/env bash
# Stable HeyDonna profile for long-context Claude development slots.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

[ -r "$ROOT/.env" ] || {
  echo "no $ROOT/.env; copy .env.sample to .env first" >&2
  exit 2
}

# Load the pinned model revisions and API-key file, then force the settings that
# differ from the generic recipe. MAX_RUNNING is deliberately not overridable:
# a stale value of 16 left too little KV capacity for concurrent agent contexts.
# shellcheck disable=SC1091
source "$ROOT/.env"
export NAME=qwen38-pango
export PORT=30000
export MAX_RUNNING=4
export MEM_FRACTION=0.65
export CTX=262144

exec "$ROOT/serve.sh"
