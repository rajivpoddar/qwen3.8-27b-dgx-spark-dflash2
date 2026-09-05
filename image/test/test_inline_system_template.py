"""CPU-only proof using the pinned, already-cached target tokenizer."""
import copy
import types
from pathlib import Path
from transformers import AutoTokenizer
from sglang.srt.entrypoints.anthropic.serving import AnthropicServing
from sglang.srt.entrypoints.anthropic.protocol import AnthropicMessagesRequest

path = '/root/.cache/huggingface/hub/models--RadixArk--Qwen3.8-27B-NVFP4/snapshots/554ebba9b5f1b79dc11246341960360e6ef05ef4'
t = AutoTokenizer.from_pretrained(path, local_files_only=True)
original = t.chat_template
patched = Path('/opt/pango-patches/qwen-inline-system.jinja').read_text()
base = [{'role':'system','content':'Stable instructions.'}, {'role':'user','content':'Hello.'}]
old = t.apply_chat_template(base, tokenize=False, enable_thinking=False, add_generation_prompt=True)
t.chat_template = patched
assert old == t.apply_chat_template(base, tokenize=False, enable_thinking=False, add_generation_prompt=True)
serving = AnthropicServing(types.SimpleNamespace(tokenizer_manager=types.SimpleNamespace(tokenizer=t)))
assert not serving._merge_inline_system
messages = [{'role':'user','content':'reference alpha beta gamma\n'*500}, {'role':'system','content':'budget 90000'}]

def render(messages):
    request = AnthropicMessagesRequest(model='qwen3.8-27b',system='Stable instructions.',messages=messages,max_tokens=32)
    converted = serving._convert_to_chat_completion_request(request)
    ms = [m.model_dump(exclude_none=True) if hasattr(m,'model_dump') else m for m in converted.messages]
    assert ms[0]['content']=='Stable instructions.'
    assert [m['role'] for m in ms].count('system') == 1 + sum(m['role']=='system' for m in messages)
    # Compare the input history, not the generation stub: Qwen legitimately
    # rewrites the old assistant thinking stub after a subsequent user query.
    text=t.apply_chat_template(ms,tokenize=False,enable_thinking=False,add_generation_prompt=False)
    return t.encode(text,add_special_tokens=False)

a=render(messages)
b=render(messages+[{'role':'assistant','content':'Done.'},{'role':'user','content':'Continue.'},{'role':'system','content':'budget 80000'}])
if a != b[:len(a)]:
    k=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
    print('prefix diagnostic',len(a),len(b),k,repr(t.decode(a[max(0,k-10):k+20])),repr(t.decode(b[max(0,k-10):k+20])))
assert a == b[:len(a)], 'new inline reminder must not invalidate earlier prefix'
print('PASS vanilla template parity, inline system-role preservation, append-only prefix:',len(a),'tokens')
