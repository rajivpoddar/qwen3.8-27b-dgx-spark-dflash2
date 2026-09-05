# Anthropic stream and cache repair

Server-only repair on the existing Pango fairness image. Same model, draft,
memory, context, endpoint, key, scheduler, and Claude sessions.

- `image/anthropic_liveness.py` emits valid Anthropic ping events every 10 seconds
  during upstream silence. It retains one pending upstream read, preserves all
  original frames, cancels/joins on disconnect, and fails after 900 seconds of
  upstream silence rather than masking an indefinitely stalled backend.
- `image/qwen-inline-system.jinja` differs from the pinned target template only
  in rendering inline system messages in sequence. It preserves the system role
  and prevents the API adapter from hoisting changing reminders ahead of history.
- `image/Dockerfile.stream-fix` verifies the exact original serving.py SHA before
  applying the small wrapper patch and running focused unit tests.

Base image: `sha256:6fa3424b7b470632addc9d63edab4f5fd4e80cf0c73c0e48a913c5094169838a`.
Candidate image: `sha256:db815495d86fa23ffa3c898ca48d3dcb5e2a09240a092fd99e4601bd53274bfa`.
Explicit additional server argument:
`--chat-template /opt/pango-patches/qwen-inline-system.jinja`.

Activation is in `activate-stream-fix.py`; it clones the actual running Docker
configuration instead of the older generic serve profile. Do not use
`serve-heydonna.sh` as a reproduction of the live tuned configuration.

Rollback (pause active requests first): stop `qwen38-pango`, rename it to an
unused failure-preservation name, rename
`qwen38-pango-before-stream-fix-20260905` back to `qwen38-pango`, then start it
and prove authenticated API readiness. The backup contains the exact previous
image and configuration; it does not need rebuilding or model downloads.

Focused proof: heartbeat/cleanup/error/timeout unit tests, CPU-only template
parity/prefix test, then a real Anthropic long-tool-argument request and its
warm follow-up. Raw tool arguments are never executed during the API test.

## Activated proof, 2026-09-05

- All four liveness tests passed, including pending-read cancellation and
  bounded upstream silence. CPU template parity/role/prefix test passed.
- Real cold request: 14,058 input tokens, valid 200-line/5,799-character tool
  argument, 23.02 seconds total, 10.014 seconds maximum event gap, one ping,
  valid tool_use and message_stop.
- Follow-up after changed inline reminder: 15,872 cached + 266 new tokens
  (98.35% reuse), 0.662 seconds total, valid tool JSON and message_stop.
- Client cancellation: running and queued requests both zero after three
  seconds. No hanging request remained.
- This is a functional streaming/cache test, not a representative TPS benchmark
  and not a greater-than-three-minute live workload stress test.
- MoP restored: new PID 45457, Node 22.13.1 / ABI 127, release
  d0299ced6a061c3cb82597d7a2054c98f5f18d4a, health OK.
- No slot process was exited or relaunched. S4 PID 38709/session
  08598482-73dc-470a-a2dc-51d4aa75f1ad was resumed directly in place.
- S4 live pickup: new Bash tool response at 03:22:27.529 UTC; next request
  reused 96,000 cached tokens and processed only 374 new tokens (99.61% reuse),
  instead of repeatedly processing the previous approximately 55K-token suffix.
- S5 PID 39055/session c8f4df2b-6e60-4ed3-8c8e-b97ed7a5ce5e resumed in place;
  existing epoch 30 unchanged and server prefill advancing. S4 epoch 637 unchanged.
