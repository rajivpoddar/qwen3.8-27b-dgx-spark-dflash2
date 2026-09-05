# Experimental prefill fairness overlay

This fork carries [SGLang PR #34058](https://github.com/sgl-project/sglang/pull/34058)
at **64b01ed86a22baa3d2788d3addbba93a0ac10b5b**. It was still **open** when
vendored; it is not a merged upstream fix or a proven DFlash2 speedup.
The vendored diff is unmodified and includes the upstream tests.

## What changes

`--max-consecutive-prefill-batches 1` reserves one runnable decode turn after
each local prefill batch. With continuous cold chunked prompts, this should
reduce long pauses in streams already generating. It does not combine prefill
and speculative decode in the same batch. **Default 0 preserves prefill-first
scheduling**, including in the candidate image.

This targets decode starvation, not peak tokens/s. A single prefill chunk can
still block output while it executes. Requests awaiting initial prefill can
still queue; the flag is not a timeout guarantee or a cache-capacity fix.
Prefill throughput and time to first token may worsen in exchange for fewer
decode pauses. No live throughput improvement has been measured for this fork.

## Build without touching the running service

Keep the existing `0.3.0` image and service intact. If the original image is
not already built, build it using `image/Dockerfile` as described in README.
Then build this separate, small overlay on the Spark:

```bash
docker build --network=none --pull=false \
  -t qwen38-27b-sglang-dflash2-sm121:0.3.0-prefill-fairness-64b01ed \
  -f image/Dockerfile.prefill-fairness image/
docker run --rm --network=none --cpus=2 --memory=6g \
  --entrypoint python \
  qwen38-27b-sglang-dflash2-sm121:0.3.0-prefill-fairness-64b01ed \
  -m unittest discover -s test/registered/scheduler -p 'test_*prefill*.py' -v
```

These steps load no model, expose no port, and request no GPU. No weights or
dependencies are downloaded. The build checks exact scheduler/server-argument
file hashes before `git apply --check`; incompatible bases fail instead of
silently replacing newer files. The other DFlash2 overlay files stay unchanged.
`BASE_IMAGE` can be supplied as a build argument for a locally pinned image ID.

## First controlled trial (requires a service cutover)

Do not run a second model server alongside the existing one. Follow the approved
Spark cutover process: fence automatic restarts/nudges and new dispatches,
interrupt slots with direct tmux, preserve the current service for rollback,
replace it, prove API readiness, then relaunch slots sequentially and have PM
re-handoff current work. Do not replay old conversations with `--continue`.
Do not restart slots until the new model is serving real inference.

Use the existing `serve.sh` environment interface; no launcher defaults were
changed by this patch. Preserve local `.env`, key/cache paths and pinned model
revisions. For the HeyDonna trial, retain the latest tuning explicitly:

```bash
# ONLY after the approved cutover has parked slots and preserved the old service.
# serve.sh removes NAME if it exists: preserve the old container first.
source .env
IMAGE=qwen38-27b-sglang-dflash2-sm121:0.3.0-prefill-fairness-64b01ed \
NAME=qwen38-pango PORT=30000 \
MAX_RUNNING=4 MEM_FRACTION=0.80 CHUNK=4096 CTX=262144 \
EXTRA_ARGS="${EXTRA_ARGS:-} --max-consecutive-prefill-batches 1" \
./serve.sh
```

Ensure an existing `EXTRA_ARGS` does not already set the same flag. Do not use
the checked-in `serve-heydonna.sh` for this A/B: it still forces the older
`MEM_FRACTION=0.65` profile. This experiment must not undo the live 0.80/4096
tuning. Leave the model, drafter, 16-token draft budget, BF16 KV/SSM, caches,
thinking setting, and four-request admission cap otherwise identical.

Readiness requires authenticated models **and a completed inference request**
through the slots' API, stable container state, and advancing engine metrics;
the launch script's tokenization check alone is insufficient. Verify the
running argument value without printing the API key or full server-args log.

## One focused proof plan

Compare limit **0 versus 1 on this same candidate image**, one server at a time.
Use the same prompts and sampling, and distinguish warm and cold prefix runs:

1. Start a sufficiently long streaming coding response. After it emits tokens,
   submit a distinct 32k-64k cold prompt, confirming their execution overlaps.
2. Record the longest output-chunk gap on the first stream, TTFT of the cold
   request, completed output tokens divided by wall time, and errors/timeouts.
   Streaming chunks may contain several speculative tokens: do not call a
   chunk-gap measurement per-token latency.
3. Repeat three times with equivalent distinct cold prefixes, then check the
   intended concurrent slot workload. Keep only if decode pauses consistently
   shrink without stalled requests, corrupted/tool-call responses, or an
   unacceptable regression in end-to-end completion time.

The extra recipe CPU tests cover sustained-prefill alternation, empty and
prefill-only running batches, decode batches becoming empty, DLLM bypass,
pending chunk preservation/resumption, and CLI flag/default registration.
These scheduler tests mock workers and batches; they do **not** prove GPU/KV
correctness, production API behavior, or improved throughput.

Validated on Spark, 2026-09-05: guarded patch application and Python compilation
passed; all **16 CPU tests passed** (9 upstream, 7 recipe regressions). Candidate
image ID: `sha256:6fa3424b7b470632addc9d63edab4f5fd4e80cf0c73c0e48a913c5094169838a`.
The running `qwen38-pango` service remained on its original image with zero
restarts. The GPU/API A/B trial above has **not** been run.

Rollback: restore the preserved original image/service and its exact launch
configuration using the same readiness checks and PM re-handoff process.
For an A/B baseline only, restart the candidate with the flag set to 0; this
disables the limiter but is not a substitute for restoring the original image
if the patch causes runtime errors. No live flag reload is provided.
