"""Offline, non-destructive candidate launcher. No slot or MoP operations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys

PROFILE = json.loads(Path(__file__).with_name("profile.json").read_text())
LABEL = "io.heydonna.recipe=qwopus-nextn"


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def verify_model(path, full_hash=False):
    for name, expected in PROFILE["shards"].items():
        file = path / name
        if file.stat().st_size != expected["size"]:
            raise ValueError(f"Incomplete shard: {name}")
        if full_hash:
            digest = hashlib.sha256()
            with file.open("rb") as source:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected["sha256"]:
                raise ValueError(f"SHA256 mismatch: {name}")
    for name in ("config.json", "hf_quant_config.json", "tokenizer.json",
                 "tokenizer_config.json", "generation_config.json",
                 "processor_config.json", "chat_template.jinja"):
        if not (path / name).is_file():
            raise ValueError(f"Missing {name}")
    config = json.loads((path / "config.json").read_text())
    if config["text_config"]["mtp_num_hidden_layers"] != 1:
        raise ValueError("Expected the native one-layer MTP head")
    index = json.loads((path / "model.safetensors.index.json").read_text())
    if set(index["weight_map"].values()) != set(PROFILE["shards"]):
        raise ValueError("Unexpected shard index")
    if not any("mtp" in key.lower() for key in index["weight_map"]):
        raise ValueError("Missing MTP tensors")


def server_args():
    p = PROFILE
    return [
        "--model-path", "/model", "--served-model-name", p["alias"],
        "--host", "0.0.0.0", "--port", str(p["port"]), "--trust-remote-code",
        "--quantization", "modelopt_mixed",
        "--context-length", str(p["context"]),
        "--max-running-requests", str(p["max_running"]),
        "--mem-fraction-static", str(p["mem_fraction"]),
        "--chunked-prefill-size", str(p["chunk"]),
        "--attention-backend", "flashinfer", "--kv-cache-dtype", "fp8_e4m3",
        "--mamba-ssm-dtype", "bfloat16", "--disable-prefill-cuda-graph",
        "--tool-call-parser", "qwen", "--reasoning-parser", "qwen3",
        "--default-chat-template-kwargs",
        '{"enable_thinking":false,"preserve_thinking":false}',
        "--speculative-algorithm", "NEXTN",
        "--speculative-draft-model-path", "/model",
        "--speculative-draft-model-quantization", "modelopt_mixed",
        "--speculative-num-steps", "2", "--speculative-eagle-topk", "1",
        "--speculative-num-draft-tokens", "3", "--enable-metrics",
    ]


def docker_command(args):
    p = PROFILE
    return [
        "docker", "run", "-d", "--name", p["container"], "--label", LABEL,
        "--restart", "no", "--gpus", "all", "--shm-size", "32g", "--ipc=host",
        "--cpuset-cpus", "5-9,15-19", "-p", f'{p["port"]}:{p["port"]}',
        "-e", "HF_HUB_OFFLINE=1", "-e", "TRANSFORMERS_OFFLINE=1",
        "-v", f"{args.model_dir}:/model:ro",
        "-v", f"{args.key_file}:/run/secrets/api-key:ro",
        "-v", f"{args.cache_dir}:/root/.cache/sglang",
        "--entrypoint", "bash", args.image,
        "-c", 'exec sglang serve "$@" --api-key "$(cat /run/secrets/api-key)"',
        "sglang", *server_args(),
    ]


def require_stopped_gpu():
    # Also catches non-Docker GPU servers. Fail closed if nvidia-smi fails.
    pids = run("nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader")
    if pids:
        raise ValueError("GPU compute processes remain; stop the source through the approved cutover first")
    names = run("docker", "ps", "-a", "--format", "{{.Names}}").splitlines()
    if PROFILE["container"] in names:
        raise ValueError("Candidate container already exists; preserve/inspect it instead of overwriting it")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PROFILE["port"])) == 0:
            raise ValueError("Serving port is occupied")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify", "command", "start"])
    parser.add_argument("--model-dir", type=Path, default=Path.home() / "models/qwopus-nvfp4-e1fad175")
    parser.add_argument("--key-file", type=Path, default=Path.home() / ".config/qwen38/api-key")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / "sglang-cache-qwopus-nextn")
    parser.add_argument("--image", default=PROFILE["image"])
    parser.add_argument("--full-hash", action="store_true")
    args = parser.parse_args()
    args.model_dir = args.model_dir.expanduser().resolve()
    args.key_file = args.key_file.expanduser().resolve()
    args.cache_dir = args.cache_dir.expanduser().resolve()
    if not args.image.startswith("sha256:") or len(args.image) != 71:
        parser.error("Pass a pinned local sha256 image ID, not a mutable tag")
    if args.action == "command":
        print(shlex.join(docker_command(args)))
        return
    verify_model(args.model_dir, full_hash=args.full_hash)
    if args.action == "verify":
        print("MODEL_FILES_VERIFIED" + ("_SHA256" if args.full_hash else "_SIZE_ONLY"))
        return
    run("docker", "image", "inspect", args.image, "--format", "{{.Id}}")
    require_stopped_gpu()
    if not args.key_file.is_file() or not args.key_file.read_text().strip():
        raise ValueError("Missing/empty API key file")
    if args.key_file.stat().st_mode & 0o077:
        raise ValueError("API key file must not be group/world accessible")
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    print(run(*docker_command(args)))
    print("STARTED_NOT_READY: run the authenticated API check before relaunching slots")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        sys.exit(1)
