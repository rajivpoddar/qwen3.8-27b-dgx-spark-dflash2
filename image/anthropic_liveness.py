"""Keep buffered Anthropic tool streams alive without altering their payloads."""
import asyncio
import time
from contextlib import suppress

import anyio


async def with_heartbeats(stream, interval=10.0, idle_limit=900.0):
    """Wait on ONE upstream read; a ping must never cancel/restart that read.

    Bound silence even with heartbeats. On expiry, fail the response rather
    than invent successful completion. Closing the wrapped generator and the
    existing StreamingResponse abort task release the backend request.
    """
    iterator = stream.__aiter__()
    pending = None
    last_event = time.monotonic()
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(iterator.__anext__())
            remaining = idle_limit - (time.monotonic() - last_event)
            if remaining <= 0:
                raise TimeoutError("Anthropic backend stream idle limit exceeded")
            done, _ = await asyncio.wait(
                {pending}, timeout=min(interval, remaining)
            )
            if not done:
                if time.monotonic() - last_event >= idle_limit:
                    raise TimeoutError("Anthropic backend stream idle limit exceeded")
                yield 'event: ping\ndata: {"type":"ping"}\n\n'
                continue
            completed, pending = pending, None
            try:
                event = completed.result()
            except StopAsyncIteration:
                return
            last_event = time.monotonic()
            yield event
    finally:
        # Starlette disconnect cancellation uses an AnyIO cancel scope. Shield
        # cleanup so the in-flight generator read is actually joined.
        with anyio.CancelScope(shield=True):
            if pending is not None:
                pending.cancel()
                with suppress(asyncio.CancelledError):
                    await pending
            close = getattr(iterator, "aclose", None)
            if close is not None:
                await close()
