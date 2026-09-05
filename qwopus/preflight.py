"""CPU-only import/config/template check; does not load weights or prove serving."""
import argparse
import json
from pathlib import Path

from serve import server_args
from transformers import AutoConfig, AutoTokenizer
from sglang.srt.server_args import ServerArgs
from sglang.srt.layers.quantization.modelopt_quant import ModelOptMixedPrecisionConfig
from sglang.srt.function_call.function_call_parser import FunctionCallParser

root = Path("/model")
parser = argparse.ArgumentParser()
ServerArgs.add_cli_args(parser)
args = parser.parse_args(server_args())
assert args.speculative_algorithm == "NEXTN"
assert args.speculative_num_steps == 2 and args.speculative_num_draft_tokens == 3
assert args.quantization == args.speculative_draft_model_quantization == "modelopt_mixed"
assert args.tool_call_parser in FunctionCallParser.ToolCallParserEnum
config = AutoConfig.from_pretrained(root, local_files_only=True, trust_remote_code=True)
assert config.text_config.mtp_num_hidden_layers == 1
quant = ModelOptMixedPrecisionConfig.from_config(config.quantization_config)
assert quant._resolve_quant_algo("model.language_model.layers.0.mlp.gate_proj") == "W4A16_NVFP4"
assert quant._resolve_quant_algo("model.language_model.layers.0.linear_attn.in_proj_qkv") == "FP8"
tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True, trust_remote_code=True)
prompt = tokenizer.apply_chat_template(
    [{"role": "user", "content": "Read the current directory with a tool."}],
    tools=[{"type": "function", "function": {
        "name": "pwd", "description": "Return current directory",
        "parameters": {"type": "object", "properties": {}}
    }}],
    tokenize=False, add_generation_prompt=True, enable_thinking=False,
)
assert "pwd" in prompt and "tool_call" in prompt
print(json.dumps({"status": "CPU_PREFLIGHT_PASS", "architecture": config.architectures,
                  "mtp_layers": config.text_config.mtp_num_hidden_layers,
                  "parser": args.tool_call_parser, "weight_loading_tested": False}))
