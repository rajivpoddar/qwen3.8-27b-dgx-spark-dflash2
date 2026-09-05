#!/usr/bin/env bash
# Preparation only. No GPU, port binding, service stops, or slot operations.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MODEL_DIR=${MODEL_DIR:-$HOME/models/qwopus-nvfp4-e1fad175}
IMAGE_ID=${IMAGE_ID:-$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$ROOT/profile.json")}
docker image inspect "$IMAGE_ID" --format '{{.Id}}'
mkdir -p "$MODEL_DIR"
docker run --rm --name qwopus-nextn-download \
  --user "$(id -u):$(id -g)" --cpus=2 --memory=4g \
  -e HOME=/tmp -e HF_HOME=/tmp/hf -e HF_HUB_DISABLE_PROGRESS_BARS=1 \
  -v "$MODEL_DIR:/model" -v "$ROOT/download.py:/download.py:ro" \
  --entrypoint python "$IMAGE_ID" /download.py
python3 "$ROOT/serve.py" verify --model-dir "$MODEL_DIR" --full-hash
docker run --rm --network=none --cpus=2 --memory=6g \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v "$MODEL_DIR:/model:ro" -v "$ROOT:/recipe:ro" \
  --entrypoint python "$IMAGE_ID" /recipe/preflight.py
echo 'PREPARED_NOT_SERVING: GPU load and API trial require a controlled cutover.'
