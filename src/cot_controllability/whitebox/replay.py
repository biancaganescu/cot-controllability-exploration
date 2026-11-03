"""Rebuild the exact token sequence the model saw while it wrote one step's reasoning.

A trial record keeps every request (messages, tools, chat-template kwargs) and every response. The
prompt of step i is the chat template applied to request i with the generation prompt (for Qwen3.6
it ends with "<think>\\n"); the reasoning the model then wrote is response i's `reasoning`. The prompt
is checked against vLLM's `usage.prompt_tokens`, so a template or tokenizer mismatch fails loudly.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass


@dataclass
class Replay:
    ids: list[int]                       # prompt tokens + reasoning tokens
    reasoning_start: int                 # index in `ids` of the first reasoning token
    reasoning: str                       # the step's reasoning text
    offsets: list[tuple[int, int]]       # char span in `reasoning` of each reasoning token
    expected_prompt_tokens: int | None   # vLLM's count, for the check

    @property
    def prompt_ok(self):
        return self.expected_prompt_tokens is None or self.expected_prompt_tokens == self.reasoning_start

    def token_at(self, char):
        """Index in `ids` of the last reasoning token that ends at or before `char` (the state from
        which the model writes the text starting at `char`); the last prompt token if none does."""
        last = self.reasoning_start - 1
        for i, (_, end) in enumerate(self.offsets):
            if end > char:
                break
            last = self.reasoning_start + i
        return last


def template_messages(messages):
    """Request messages as the chat template expects them: vLLM sends tool-call arguments as JSON
    strings, the Qwen template iterates over them as a mapping."""
    out = copy.deepcopy(messages)
    for m in out:
        for call in m.get('tool_calls') or []:
            args = call['function'].get('arguments')
            if isinstance(args, str):
                call['function']['arguments'] = json.loads(args)
    return out


def replay(trial, step, tokenizer):
    """Replay of `trial`'s step `step` (0-based index into requests/responses)."""
    request, response = trial['requests'][step], trial['responses'][step]
    prompt = tokenizer.apply_chat_template(
        template_messages(request['messages']), tools=request.get('tools'), add_generation_prompt=True,
        tokenize=False, **request.get('chat_template_kwargs', {}))
    prompt_ids = tokenizer(prompt, add_special_tokens=False).input_ids
    reasoning = response['choices'][0]['message'].get('reasoning') or ''
    encoded = tokenizer(reasoning, add_special_tokens=False, return_offsets_mapping=True)
    return Replay(ids=list(prompt_ids) + list(encoded.input_ids), reasoning_start=len(prompt_ids),
                  reasoning=reasoning, offsets=[tuple(o) for o in encoded.offset_mapping],
                  expected_prompt_tokens=(response.get('usage') or {}).get('prompt_tokens'))
