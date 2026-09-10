#!/usr/bin/env bash
# TURBO-Fable target on Pango's patched SGLang image, using the checkpoint's
# native MTP/EAGLE head instead of the base-model DFlash2 drafter.
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

export IMAGE=${IMAGE:-qwen38-pango-heydonna:stream-fix-a4a6feb}
export NAME=qwen38-turbo-fable-pango-native-mtp
export PORT=30000
export MODEL=SeatownSin/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU-NVFP4-W4A16
export REVISION=8c0067b9f7b909906d51042099907fd0cdf1e82d
export SPEC=0
export MAX_RUNNING=4
export MEM_FRACTION=0.65
export CHUNK=2048
export KV_DTYPE=bfloat16
export SSM_DTYPE=bfloat16
export CTX=262144
export EXTRA_ARGS="${EXTRA_ARGS:-} --speculative-algorithm EAGLE --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4 --max-consecutive-prefill-batches 1 --chat-template /opt/pango-patches/qwen-inline-system.jinja"

if [ "${DRY_RUN:-0}" = 1 ]; then
  printf '%s\n' \
    "IMAGE=$IMAGE" \
    "NAME=$NAME" \
    "PORT=$PORT" \
    "MODEL=$MODEL" \
    "REVISION=$REVISION" \
    "SPEC=$SPEC" \
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
