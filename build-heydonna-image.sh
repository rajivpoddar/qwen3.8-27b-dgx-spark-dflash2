#!/usr/bin/env bash
# Build the Pango engine plus the HeyDonna prefill-fairness and Anthropic
# stream/cache overlays. This does not start a model server or use the GPU.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BASE_IMAGE=${BASE_IMAGE:-qwen38-27b-sglang-dflash2-sm121:0.3.0}
FAIRNESS_IMAGE=${FAIRNESS_IMAGE:-qwen38-pango-fairness-base:64b01ed}
HEYDONNA_IMAGE=${HEYDONNA_IMAGE:-qwen38-pango-heydonna:stream-fix-a4a6feb}

docker build \
  -t "$BASE_IMAGE" \
  -f "$ROOT/image/Dockerfile" \
  "$ROOT/image"

docker build --network=none --pull=false \
  --build-arg "BASE_IMAGE=$BASE_IMAGE" \
  -t "$FAIRNESS_IMAGE" \
  -f "$ROOT/image/Dockerfile.prefill-fairness" \
  "$ROOT/image"

docker build --network=none --pull=false \
  --build-arg "BASE_IMAGE=$FAIRNESS_IMAGE" \
  -t "$HEYDONNA_IMAGE" \
  -f "$ROOT/image/Dockerfile.stream-fix" \
  "$ROOT/image"

printf 'built %s\n' "$HEYDONNA_IMAGE"
