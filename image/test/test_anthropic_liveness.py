import asyncio
import unittest
from sglang.srt.entrypoints.anthropic.liveness import with_heartbeats


class LivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_ping_keeps_single_read_and_payload(self):
        reads = []
        async def source():
            reads.append(1)
            await asyncio.sleep(.035)
            yield 'event: message_stop\ndata: {"type":"message_stop"}\n\n'
        events = [x async for x in with_heartbeats(source(), .01, 1)]
        self.assertGreaterEqual(sum('event: ping' in x for x in events), 2)
        self.assertEqual(reads, [1])
        self.assertTrue(events[-1].startswith('event: message_stop'))

    async def test_disconnect_closes_pending_read(self):
        closed = asyncio.Event()
        async def source():
            try:
                await asyncio.sleep(60)
                yield 'unreachable'
            finally:
                closed.set()
        stream = with_heartbeats(source(), .01, 1)
        self.assertIn('event: ping', await anext(stream))
        await stream.aclose()
        self.assertTrue(closed.is_set())

    async def test_silence_is_bounded(self):
        closed = asyncio.Event()
        async def source():
            try:
                await asyncio.sleep(60)
                yield 'unreachable'
            finally:
                closed.set()
        with self.assertRaises(TimeoutError):
            async for _ in with_heartbeats(source(), .01, .04):
                pass
        self.assertTrue(closed.is_set())

    async def test_error_is_not_retried_or_hidden(self):
        async def source():
            yield 'data: first\n\n'
            raise ValueError('upstream failed')
        stream = with_heartbeats(source(), .01, 1)
        self.assertEqual(await anext(stream), 'data: first\n\n')
        with self.assertRaisesRegex(ValueError, 'upstream failed'):
            await anext(stream)


if __name__ == '__main__':
    unittest.main()
