"""Run in the existing SGLang image, with the destination mounted at /model."""
from huggingface_hub import snapshot_download
import sys

snapshot_download(
    repo_id="sojufx/Qwopus3.8-27B-Flash-NVFP4",
    revision="e1fad175b1f069b9e19a0293c561cefb516df7e4",
    local_dir="/model",
    max_workers=2,
    allow_patterns=["*.json", "*.jinja"] if "--metadata-only" in sys.argv else None,
)
print("QWOPUS_METADATA_COMPLETE" if "--metadata-only" in sys.argv else "QWOPUS_DOWNLOAD_COMPLETE", flush=True)
