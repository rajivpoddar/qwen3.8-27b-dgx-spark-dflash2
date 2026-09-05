import argparse
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import serve


class RecipeTests(unittest.TestCase):
    def test_native_mtp_not_dflash(self):
        args = serve.server_args()
        self.assertEqual(args[args.index("--speculative-algorithm") + 1], "NEXTN")
        self.assertNotIn("DFLASH", args)
        self.assertNotIn("--max-consecutive-prefill-batches", args)
        self.assertEqual(args[args.index("--speculative-num-steps") + 1], "2")
        self.assertEqual(args[args.index("--speculative-num-draft-tokens") + 1], "3")

    def test_command_does_not_read_or_embed_credentials(self):
        args = argparse.Namespace(model_dir=Path("/model-data"), key_file=Path("/private/key"),
                                  cache_dir=Path("/cache"), image=serve.PROFILE["image"])
        with patch.object(Path, "read_text", side_effect=AssertionError("read secret")):
            command = serve.docker_command(args)
        self.assertIn("/private/key:/run/secrets/api-key:ro", command)
        self.assertIn("HF_HUB_OFFLINE=1", command)
        self.assertEqual(command[command.index("--restart") + 1], "no")
        self.assertNotIn("--rm", command)
        self.assertEqual(command[command.index("--speculative-draft-model-path") + 1], "/model")

    @patch("serve.run", return_value="1234")
    def test_refuses_gpu_co_tenant(self, _run):
        with self.assertRaisesRegex(ValueError, "GPU compute"):
            serve.require_stopped_gpu()

    @patch("serve.run", side_effect=["", "qwopus-nextn"])
    def test_preserves_existing_candidate(self, _run):
        with self.assertRaisesRegex(ValueError, "already exists"):
            serve.require_stopped_gpu()

    @patch("serve.socket.socket")
    @patch("serve.run", side_effect=["", ""])
    def test_refuses_occupied_port(self, _run, sock):
        sock.return_value.__enter__.return_value.connect_ex.return_value = 0
        with self.assertRaisesRegex(ValueError, "port is occupied"):
            serve.require_stopped_gpu()

    @patch("serve.socket.socket")
    @patch("serve.run", side_effect=["", ""])
    def test_accepts_empty_gpu_and_free_port(self, _run, sock):
        sock.return_value.__enter__.return_value.connect_ex.return_value = 111
        serve.require_stopped_gpu()

    def test_rejects_incomplete_shard(self):
        directory = MagicMock()
        directory.__truediv__.return_value.stat.return_value.st_size = 1
        with self.assertRaisesRegex(ValueError, "Incomplete shard"):
            serve.verify_model(directory)


if __name__ == "__main__":
    unittest.main()
