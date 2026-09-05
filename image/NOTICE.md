# Engine image overlay

`Dockerfile` builds `qwen38-27b-sglang-dflash2-sm121:0.3.0`: the pinned day-0
Qwen3.8-27B SGLang image (`lmsysorg/sglang:qwen38-27b`, digest in the Dockerfile)
plus the files touched by two upstream SGLang pull requests, copied verbatim
from `sgl-project/sglang`:

- #35371 "DFlash2: local convolution + candidate selector" (merge c14312a)
- #35496 "Support quantized target lm_head in the DFlash2 selector"

Six runtime files and two unit tests, pure Python, no CUDA build. They are
SGLang code under the Apache License 2.0; copyright the SGLang contributors.
The overlay approach and label scheme follow r0b0tlab's community image.

```bash
docker build -t qwen38-27b-sglang-dflash2-sm121:0.3.0 -f image/Dockerfile image/
```

After boot, `serve.sh` greps the log for `kept eager (reason=quantized lm_head)`;
if that line appears, #35496 is missing and the selector runs outside the draft
CUDA graph.

## Experimental scheduler overlay

`Dockerfile.prefill-fairness` adds the unmodified diff of upstream SGLang
[PR #34058](https://github.com/sgl-project/sglang/pull/34058), pinned to
`64b01ed86a22baa3d2788d3addbba93a0ac10b5b`, on top of the original image.
`patches/34058-64b01ed.patch` contains three runtime-file changes and one
upstream test file, under SGLang's Apache License 2.0, copyright the SGLang
contributors. The PR was open at vendoring time. Recipe-specific CPU regressions
are added separately; the upstream patch itself has not been modified.
See [PREFILL_FAIRNESS.md](../PREFILL_FAIRNESS.md) for the isolated build, opt-in
flag, validation limits, and rollback. The original Dockerfile is unchanged.
