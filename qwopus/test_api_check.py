import io
import json
import unittest
from unittest.mock import patch

import check_api


class APICheckTests(unittest.TestCase):
    def responses(self):
        return [
            {"data": [{"id": check_api.PROFILE["alias"]}]},
            {"stop_reason": "tool_use", "content": [
                {"type": "tool_use", "id": "probe-1", "name": "report_probe",
                 "input": {"value": "READY"}}]},
            {"stop_reason": "end_turn", "content": [{"type": "text", "text": "READY"}]},
        ]

    def invoke(self, responses):
        streams = [io.BytesIO(json.dumps(r).encode()) for r in responses]
        with patch("sys.argv", ["check_api.py"]), \
             patch("check_api.Path.read_text", return_value="test-key"), \
             patch("check_api.urllib.request.urlopen", side_effect=streams) as request, \
             patch("builtins.print"):
            check_api.main()
        return request.call_args_list

    def test_structured_roundtrip(self):
        calls = self.invoke(self.responses())
        self.assertEqual(len(calls), 3)
        final_payload = json.loads(calls[-1].args[0].data)
        self.assertEqual(final_payload["messages"][-1]["content"][0]["tool_use_id"], "probe-1")

    def test_wrong_model_fails(self):
        responses = self.responses()
        responses[0] = {"data": [{"id": "qwen3.8-27b"}]}
        with self.assertRaisesRegex(AssertionError, "Wrong model"):
            self.invoke(responses)

    def test_tool_arguments_must_match(self):
        responses = self.responses()
        responses[1]["content"][0]["input"]["value"] = "wrong"
        with self.assertRaisesRegex(AssertionError, "Incorrect tool arguments"):
            self.invoke(responses)

    def test_unfinished_response_fails(self):
        responses = self.responses()
        responses[2]["stop_reason"] = "max_tokens"
        with self.assertRaisesRegex(AssertionError, "did not terminate"):
            self.invoke(responses)


if __name__ == "__main__":
    unittest.main()
