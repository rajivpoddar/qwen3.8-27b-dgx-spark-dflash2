"""Recipe regressions against the real, patched Scheduler (CPU-only)."""

import argparse
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_consecutive_prefill_limiter import (
    ConsecutivePrefillLimiter,
    Scheduler,
    _Batch,
    _make_scheduler,
)

from sglang.srt.server_args import ServerArgs


@patch("sglang.srt.managers.scheduler.set_schedule_time_batch")
class TestRecipeFairness(unittest.TestCase):
    def make_scheduler(self, running_batch):
        prefill = _Batch()
        scheduler = _make_scheduler(
            ConsecutivePrefillLimiter(1),
            SimpleNamespace(batch_to_run=prefill, running_batch=running_batch),
        )
        scheduler.update_running_batch.return_value = running_batch
        return scheduler, prefill

    def test_alternates_under_continuous_prefill(self, _schedule_time):
        running = _Batch()
        scheduler, prefill = self.make_scheduler(running)
        batches = [
            Scheduler.get_next_batch_to_run(scheduler, running, None).batch_to_run
            for _ in range(6)
        ]
        self.assertEqual(batches, [prefill, running] * 3)

    def test_empty_running_batch_keeps_prefilling(self, _schedule_time):
        running = _Batch(empty=True)
        scheduler, prefill = self.make_scheduler(running)
        for _ in range(3):
            plan = Scheduler.get_next_batch_to_run(scheduler, running, None)
            self.assertIs(plan.batch_to_run, prefill)
        scheduler.update_running_batch.assert_not_called()

    def test_prefill_only_batch_does_not_force_decode(self, _schedule_time):
        running = _Batch(prefill_only=True)
        running.filter_batch = Mock()
        scheduler, prefill = self.make_scheduler(running)
        for _ in range(3):
            plan = Scheduler.get_next_batch_to_run(scheduler, running, None)
            self.assertIs(plan.batch_to_run, prefill)
        scheduler.update_running_batch.assert_not_called()

    def test_decode_that_becomes_empty_is_not_returned(self, _schedule_time):
        running = _Batch()
        scheduler, _ = self.make_scheduler(running)
        scheduler.consecutive_prefill_limiter.on_prefill()
        scheduler.update_running_batch.return_value = _Batch(empty=True)
        plan = Scheduler.get_next_batch_to_run(scheduler, running, None)
        self.assertIsNone(plan.batch_to_run)
        self.assertTrue(plan.running_batch.is_empty())

    def test_dllm_remains_on_its_existing_path(self, _schedule_time):
        running = _Batch()
        scheduler, prefill = self.make_scheduler(running)
        scheduler.dllm_config = object()
        scheduler.dllm_manager = Mock()
        scheduler.dllm_manager.any_staging_reqs.return_value = False
        scheduler.get_new_batch_dllm = Mock(return_value=prefill)
        scheduler.consecutive_prefill_limiter.on_prefill()
        plan = Scheduler.get_next_batch_to_run(scheduler, running, None)
        self.assertIs(plan.batch_to_run, prefill)
        scheduler.get_new_batch_dllm.assert_called_once_with(running)
        scheduler.get_new_batch_prefill.assert_not_called()
        scheduler.update_running_batch.assert_not_called()

    def test_pending_chunk_survives_decode_and_prefill_resumes(self, _schedule_time):
        running = _Batch()
        scheduler, prefill = self.make_scheduler(running)
        chunk = Mock()
        chunk.extend_range.end = 4096
        chunk.prefix_indices = []
        scheduler.chunked_req = chunk
        scheduler.stash_chunked_request = Mock()
        scheduler.consecutive_prefill_limiter.on_prefill()

        decode = Scheduler.get_next_batch_to_run(scheduler, running, None)
        self.assertIs(decode.batch_to_run, running)
        self.assertIs(scheduler.chunked_req, chunk)
        scheduler.get_new_batch_prefill.assert_not_called()
        scheduler.stash_chunked_request.assert_called_once_with(chunk)

        resumed = Scheduler.get_next_batch_to_run(scheduler, running, None)
        self.assertIs(resumed.batch_to_run, prefill)
        self.assertIs(scheduler.chunked_req, chunk)
        scheduler.get_new_batch_prefill.assert_called_once_with(running)


class TestRecipeCLI(unittest.TestCase):
    def test_flag_is_registered_with_disabled_default(self):
        parser = argparse.ArgumentParser()
        ServerArgs.add_cli_args(parser)
        args = parser.parse_args(["--model-path", "unused"])
        self.assertEqual(args.max_consecutive_prefill_batches, 0)
        args = parser.parse_args([
            "--model-path", "unused", "--max-consecutive-prefill-batches", "1"
        ])
        self.assertEqual(args.max_consecutive_prefill_batches, 1)


if __name__ == "__main__":
    unittest.main()
