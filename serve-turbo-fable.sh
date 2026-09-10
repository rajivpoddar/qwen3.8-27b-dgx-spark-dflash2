#!/usr/bin/env bash
# TURBO-Fable target on Pango's DFlash2 engine with the HeyDonna fairness and
# Anthropic streaming/cache repairs. It starts only the inference service.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

ENV_FILE=${ENV_FILE:-$ROOT/.env}
if [ -r "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
elif [ "${DRY_RUN:-0}" != 1 ]; then
  echo "no $ENV_FILE; copy .env.sample to .env first" >&2
  exit 2
fi

# Load only local key/cache choices, then pin every model and serving value that
# defines this profile. This prevents stale benchmark exports from silently
# selecting the base checkpoint or the 16-seat short-prompt profile.
export IMAGE=${IMAGE:-qwen38-pango-heydonna:stream-fix-a4a6feb}
export NAME=qwen38-turbo-fable-pango
export PORT=30000
export MODEL=SeatownSin/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU-NVFP4-W4A16
export REVISION=8c0067b9f7b909906d51042099907fd0cdf1e82d
export DRAFT=maurienne-ai/Qwen3.8-27B-DFlash2-NVFP4-RTNcal
export DRAFT_REVISION=bd7a934213c47a9e7ef69eef36bb3325f47fd1f1
export DRAFT_QUANT=modelopt_fp4
export DRAFT_TOKENS=16
export MAX_RUNNING=4
export MEM_FRACTION=0.65
export CHUNK=2048
export KV_DTYPE=bfloat16
export SSM_DTYPE=bfloat16
export CTX=262144
export EXTRA_ARGS="${EXTRA_ARGS:-} --max-consecutive-prefill-batches 1 --chat-template /opt/pango-patches/qwen-inline-system.jinja"

if [ "${DRY_RUN:-0}" = 1 ]; then
  printf '%s\n' \
    "IMAGE=$IMAGE" \
    "NAME=$NAME" \
    "PORT=$PORT" \
    "MODEL=$MODEL" \
    "REVISION=$REVISION" \
    "DRAFT=$DRAFT" \
    "DRAFT_REVISION=$DRAFT_REVISION" \
    "DRAFT_TOKENS=$DRAFT_TOKENS" \
    "MAX_RUNNING=$MAX_RUNNING" \
    "MEM_FRACTION=$MEM_FRACTION" \
    "CHUNK=$CHUNK" \
    "KV_DTYPE=$KV_DTYPE" \
    "SSM_DTYPE=$SSM_DTYPE" \
    "CTX=$CTX" \
    "EXTRA_ARGS=$EXTRA_ARGS"
  exit 0
fi

exec "$ROOT/serve.sh"
