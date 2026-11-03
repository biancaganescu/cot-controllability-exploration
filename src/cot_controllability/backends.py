"""Model backends for agentic tasks: one interface over OpenRouter and a local vLLM server.

A model is a YAML file in configs/models/ (as in interptemp): `backend` picks the class,
`sampling` goes into every request, `options` are backend-specific. `backend` may also be
'module:Class' for a custom Backend subclass.
"""
from __future__ import annotations

import importlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

from cot_controllability.common import api_json, check_endpoint, reasoning_variants

CONFIG_DIR = Path(__file__).resolve().parents[2] / 'configs' / 'models'


@dataclass(frozen=True)
class ModelConfig:
    backend: str
    model: str
    max_tokens: int = 8192
    sampling: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)
    name: str = ''  # Config file stem, recorded in run manifests.

    def to_dict(self):
        return asdict(self)


def load_model_config(name_or_path):
    """Load `configs/models/<name>.yaml`, or a YAML file given by path."""
    path = Path(name_or_path)
    if path.suffix not in ('.yaml', '.yml'):
        path = CONFIG_DIR / (str(name_or_path) + '.yaml')
    if not path.exists():
        known = sorted(p.stem for p in CONFIG_DIR.glob('*.yaml'))
        raise ValueError(f'Unknown model config {name_or_path!r}. Known: {known}, or pass a .yaml path')
    raw = yaml.safe_load(path.read_text(encoding='utf-8'))
    allowed = {f.name for f in fields(ModelConfig)} - {'name'}
    if not isinstance(raw, dict) or set(raw) - allowed or not {'backend', 'model'} <= set(raw):
        raise ValueError(f'{path}: expected keys {sorted(allowed)} with backend and model set')
    return ModelConfig(name=path.stem, **raw)


class Backend(ABC):
    paid = False

    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg

    def preflight(self, first_requests, max_steps):
        """Check the live endpoint before any inference; return a snapshot for the manifest."""
        return {}

    @abstractmethod
    def request(self, messages, tools, seed=None):
        """The request body; `tools=None` sends none, `seed` is used where the backend supports it."""

    @abstractmethod
    def send(self, body): ...

    @abstractmethod
    def bound(self, raw):
        """Whether a response came from the configured model (and route)."""

    @abstractmethod
    def history_message(self, message):
        """The assistant message to append to history, keeping native reasoning."""


class OpenRouterBackend(Backend):
    paid = True
    REQUIRED_PARAMETERS = {'reasoning', 'reasoning_effort', 'max_tokens', 'tools'}
    TOOL_RESULT_BYTES = 4096  # Generous per-step allowance for the budget estimate.

    def __init__(self, cfg):
        super().__init__(cfg)
        self.price_caps = None
        self.key = None

    def profile(self):
        return {'model': self.cfg.model, 'max_tokens': self.cfg.max_tokens, **self.cfg.options}

    def preflight(self, first_requests, max_steps):
        self.key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not self.key:
            raise ValueError('Set OPENROUTER_API_KEY in the environment')
        model, endpoint, prices = check_endpoint(self.profile(), self.REQUIRED_PARAMETERS)
        estimate = 0.0
        for body in first_requests:
            base = len(json.dumps(body).encode()) + 1024
            for step in range(max_steps):
                context = base + step * (self.cfg.max_tokens + self.TOOL_RESULT_BYTES)
                estimate += context * prices[0] + self.cfg.max_tokens * prices[1]
        self.price_caps = {'prompt': prices[0] * 1e6, 'completion': prices[1] * 1e6}
        return {'model': model, 'endpoint': endpoint, 'estimated_max_usd': estimate,
                'price_caps_per_million': self.price_caps}

    def request(self, messages, tools, seed=None):
        # `seed` is ignored: the pinned endpoint does not list it, and require_parameters would
        # then reject the request.
        options = self.cfg.options
        provider = {'only': [options['provider_tag']], 'allow_fallbacks': False,
                    'require_parameters': True, 'data_collection': 'deny',
                    'quantizations': [options['quantisation']]}
        if self.price_caps:
            provider['max_price'] = self.price_caps
        body = {'model': self.cfg.model, 'messages': messages, 'provider': provider,
                'reasoning': {'enabled': True, 'exclude': False, 'effort': options['effort']},
                'max_tokens': self.cfg.max_tokens, **self.cfg.sampling}
        return {**body, 'tools': tools} if tools else body

    def send(self, body):
        return api_json('chat/completions', body, self.key)

    def bound(self, raw):
        return (isinstance(raw, dict) and not raw.get('error')
                and raw.get('model') in (self.cfg.model, self.cfg.options['canonical_slug'])
                and raw.get('provider') == self.cfg.options['provider_name'])

    def history_message(self, message):
        kept = {k: message[k] for k in ('content', 'tool_calls', 'reasoning', 'reasoning_details') if k in message}
        return {'role': 'assistant', **kept}


class VLLMBackend(Backend):
    """A model served by `infra/serve_vllm.sh` (OpenAI-compatible API, no provider routing)."""

    def __init__(self, cfg):
        super().__init__(cfg)
        base = os.environ.get('VLLM_BASE_URL') or cfg.options.get('base_url', 'http://localhost:8000/v1/')
        self.base_url = base.rstrip('/') + '/'
        self.key = os.environ.get('VLLM_API_KEY', '').strip() or None
        # Under full load each request gets a small share of the GPU, so a long reasoning reply can
        # take many minutes; only GPU time is spent while waiting.
        self.timeout = float(cfg.options.get('timeout_s', 3600))

    def preflight(self, first_requests, max_steps):
        served = [m.get('id') for m in api_json('models', key=self.key, base=self.base_url).get('data', [])]
        if self.cfg.model not in served:
            raise ValueError(f'{self.cfg.model} is not served at {self.base_url}; served: {served}')
        return {'base_url': self.base_url, 'served_models': served}

    def request(self, messages, tools, seed=None):
        body = {'model': self.cfg.model, 'messages': messages, 'max_tokens': self.cfg.max_tokens,
                **self.cfg.sampling}
        if tools:
            body['tools'] = tools
        if seed is not None:
            body['seed'] = seed
        if self.cfg.options.get('chat_template_kwargs'):
            body['chat_template_kwargs'] = self.cfg.options['chat_template_kwargs']
        return body

    def send(self, body):
        return api_json('chat/completions', body, self.key, base=self.base_url, timeout=self.timeout)

    def bound(self, raw):
        return isinstance(raw, dict) and not raw.get('error') and raw.get('model') == self.cfg.model

    def history_message(self, message):
        # Qwen chat templates read `reasoning_content`; vLLM may return it as `reasoning`.
        variants, _ = reasoning_variants(message)
        kept = {k: message[k] for k in ('content', 'tool_calls') if k in message}
        text = next(iter(variants.values()), None)
        return {'role': 'assistant', **kept, **({'reasoning_content': text} if text else {})}


BACKENDS = {'openrouter': OpenRouterBackend, 'vllm': VLLMBackend}


def build_backend(cfg: ModelConfig) -> Backend:
    if ':' in cfg.backend:
        module, _, attr = cfg.backend.partition(':')
        cls = getattr(importlib.import_module(module), attr)
    elif cfg.backend in BACKENDS:
        cls = BACKENDS[cfg.backend]
    else:
        raise ValueError(f'Unknown backend {cfg.backend!r}. Known: {sorted(BACKENDS)}, or pass module:Class')
    return cls(cfg)
