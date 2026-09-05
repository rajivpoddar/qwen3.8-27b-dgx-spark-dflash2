"""Run after an authorized service switch; proves Anthropic tool round-trip."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request

from serve import PROFILE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:30000")
    parser.add_argument("--key-file", type=Path, default=Path.home() / ".config/qwen38/api-key")
    args = parser.parse_args()
    key = args.key_file.read_text().strip()

    def request(path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(args.base_url.rstrip("/") + path, data=body,
            headers={"Authorization": f"Bearer {key}", "x-api-key": key,
                     "anthropic-version": "2023-06-01", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    models = request("/v1/models")
    assert PROFILE["alias"] in [m["id"] for m in models["data"]], "Wrong model alias"
    tools = [{"name": "report_probe", "description": "Report a probe string.",
              "input_schema": {"type": "object", "properties": {"value": {"type": "string"}},
                               "required": ["value"]}}]
    messages = [{"role": "user", "content": "Call report_probe with value READY."}]
    response = request("/v1/messages", {
        "model": PROFILE["alias"], "max_tokens": 256, "messages": messages,
        "tools": tools, "tool_choice": {"type": "tool", "name": "report_probe"},
    })
    calls = [b for b in response["content"] if b["type"] == "tool_use"]
    assert len(calls) == 1 and calls[0]["name"] == "report_probe", "No structured tool call"
    assert calls[0]["input"].get("value") == "READY", "Incorrect tool arguments"
    assert response.get("stop_reason") == "tool_use", "Incorrect tool stop reason"
    messages += [{"role": "assistant", "content": response["content"]},
                 {"role": "user", "content": [{"type": "tool_result",
                   "tool_use_id": calls[0]["id"], "content": "Probe succeeded. Reply READY."}]}]
    final = request("/v1/messages", {"model": PROFILE["alias"], "max_tokens": 128,
                    "messages": messages, "tools": tools, "tool_choice": {"type": "none"}})
    assert final.get("stop_reason") == "end_turn", "Response did not terminate"
    assert any(b["type"] == "text" and "READY" in b.get("text", "") for b in final["content"])
    assert not any(b["type"] == "thinking" for b in response["content"] + final["content"])
    print("ANTHROPIC_TOOL_ROUNDTRIP_PASS (non-streaming; real Claude streaming canary still required)")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError) as error:
        # Never print request objects/headers or the key.
        raise SystemExit(f"API_CHECK_FAILED: {error}")
