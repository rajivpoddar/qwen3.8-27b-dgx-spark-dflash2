# Qwopus NVFP4 / native NEXTN on one DGX Spark

Experimental profile in the Pango fork, derived from the [model author's
SGLang recipe](https://huggingface.co/sojufx/Qwopus3.8-27B-Flash-NVFP4).
This is NOT the older Qwopus GGUF/llama.cpp deployment or the much larger
Qwen3.8-Flash-Next model. No six-client speed or reliability claim is made.

## Pinned trial

`profile.json` pins the checkpoint revision, shard hashes, and existing local
SGLang image ID. The image is the original Pango `0.3.0` build (from this repo's
`image/Dockerfile`), with **no scheduler-fairness patch**. Its DFlash2 modules are
present but unused: target and native MTP draft both read the same `/model`.
The runtime recognizes NEXTN as an EAGLE alias; an EAGLE log is not evidence
that the wrong drafter was loaded.

| Setting | Trial value |
|---|---|
| Checkpoint | sojufx/Qwopus3.8-27B-Flash-NVFP4 |
| Revision | e1fad175b1f069b9e19a0293c561cefb516df7e4 |
| Model / draft quantization | modelopt_mixed |
| Speculation | NEXTN, steps 2, top-k 1, draft tokens 3 |
| Context / concurrent requests | 131,072 / 4 |
| Memory fraction / prefill chunk | 0.75 / 4096 |
| KV / SSM | FP8 e4m3 / BF16 |
| Thinking / tool parser | off / qwen |
| Model alias / port | qwopus3.8-27b-flash-nvfp4 / 30000 |

The model is a W4A16-NVFP4/FP8 mixture, not the stock Qwen W4A4 profile.
Resource settings are conservative experiment choices, not measured optima.
Six clients may connect, but only four requests are admitted concurrently;
the remainder queue. 131K is per-request maximum, not six reserved KV slots.
Increase context/concurrency only after inspecting actual KV and Mamba pools.

## Prepare while Pango continues serving

On the existing Spark, run from the repo root in a durable tmux session:

```bash
tmux new-session -s qwopus-prepare 'bash qwopus/prepare.sh; exec bash'
```

Preparation downloads ~21.9 GB of pinned shards and small metadata files,
checks all shard SHA256 hashes, then tests argument parsing, quantization
configuration, tokenizer/chat-template loading and native MTP metadata in a
CPU-only container. It does NOT load weights, reserve GPU memory, expose a
port, or stop the live service. Public downloads need no token; they may be
rate limited. Hugging Face resumes partial downloads in the same directory.

The checked-in image ID is a local immutable ID from Rajiv's Spark, not a
registry download. On another box, first build `image/Dockerfile` as described
in the parent README, resolve the resulting image ID, and pass `IMAGE_ID` to
preparation and `--image` to the launcher. Re-run preflight on that image.

No changes to the existing key are needed: the default path is
`~/.config/qwen38/api-key`. For another installation provision a private key
file and use `--key-file`; never commit it. The candidate uses its own tactic
cache directory so it cannot overwrite Pango's cache.

## Activate ONLY during an authorized cutover

Use the local `dgx-spark-cutover` skill. Preserve the current service/image and
rollback configuration. Interrupt all slots with direct tmux and pin their
assignments/disk state; unload MoP before changing inference services. Keep
the old interrupted Claude sessions open while the target loads. No checkpoint
prompts or `--continue`. Do not exit/relaunch slots until the target is serving.

After the source service has stopped and released the GPU:

```bash
python3 qwopus/serve.py start
# After loading completes:
python3 qwopus/check_api.py
```

The launcher refuses any GPU compute co-tenant, an occupied port, or an existing
candidate container. It never deletes/stops either model service. It uses local
weights offline, reads the API key inside the container, and uses restart policy
`no` during qualification so a failed candidate cannot fight the rollback.
`python3 qwopus/serve.py command` prints the command without reading the key.

Readiness is authenticated model discovery plus a successful Anthropic tool
call/result round-trip, stable container state and advancing engine metrics.
Run a real Claude streaming/tool canary too. Only then fresh-launch the original
panes sequentially, restore/prove MoP, and have PM re-handoff only existing
active assignments one at a time. Leave idle slots idle.

For qualification, exercise a realistic cold long prompt and its warm-prefix
follow-up, then two clients and six-client load. Record TTFT, output pauses,
completion throughput, cache reuse and errors. Six-client loading is not proven
by a short single-client canary. If requests stop advancing or tool/API behavior
fails, stop PM handoffs, stop this exact candidate (`docker stop -t 30
qwopus-nextn`), and restore the preserved Pango service. Verify rollback before
fresh-launching and PM re-handoff. Do not delete the stopped candidate or caches
to recover; retain them for diagnosis.

## Local tests

```bash
python3 -m unittest discover -s qwopus -p 'test_*.py' -v
bash -n qwopus/prepare.sh
```

CPU/config tests do not prove GPU kernels, loaded-weight correctness, API
streaming, or throughput. The new fairness patch must remain off for this first
trial so the model/decoder change can be evaluated separately.

On 2026-09-05, all 11 local launcher/API-check tests passed. The pinned Spark
image also passed the offline CPU preflight against this revision's real
configuration and tokenizer. Full GPU weight loading and live API testing
remain unperformed until an authorized cutover.
