#!/usr/bin/env bash
# Download the immutable TURBO-Fable target and Pango DFlash2 drafter into the
# cache layout consumed by serve.sh. This does not start a model server.
set -euo pipefail

MODEL=${MODEL:-SeatownSin/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU-NVFP4-W4A16}
REVISION=${REVISION:-8c0067b9f7b909906d51042099907fd0cdf1e82d}
DRAFT=${DRAFT:-maurienne-ai/Qwen3.8-27B-DFlash2-NVFP4-RTNcal}
DRAFT_REVISION=${DRAFT_REVISION:-bd7a934213c47a9e7ef69eef36bb3325f47fd1f1}
HF_CACHE=${HF_CACHE:-$HOME/models/hf}

command -v hf >/dev/null 2>&1 || {
  echo "missing hf CLI; install or upgrade huggingface_hub first" >&2
  exit 2
}

HF_HOME="$HF_CACHE" hf download "$MODEL" --revision "$REVISION"
HF_HOME="$HF_CACHE" hf download "$DRAFT" --revision "$DRAFT_REVISION"

write_ref() {
  local repo=$1 revision=$2 dir="$HF_CACHE/hub/models--${1//\//--}"
  [ -d "$dir/snapshots/$revision" ] || {
    echo "missing snapshot $repo@$revision" >&2
    exit 2
  }
  compgen -G "$dir/snapshots/$revision/*.safetensors" >/dev/null || {
    echo "snapshot $repo@$revision has no safetensors" >&2
    exit 2
  }
  mkdir -p "$dir/refs"
  printf '%s' "$revision" > "$dir/refs/main"
  printf 'prepared %s@%s\n' "$repo" "$revision"
}

write_ref "$MODEL" "$REVISION"
write_ref "$DRAFT" "$DRAFT_REVISION"
