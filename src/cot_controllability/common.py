"""Shared I/O, canary and OpenRouter helpers for all tasks."""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATA_DIR = Path(__file__).resolve().parent / 'data'
API = 'https://openrouter.ai/api/v1/'
CANARY = 'PRIVACY-DEMO-CANARY-DO-NOT-TRAIN-0f02b827-a60d-45dd-8451-93c63a585d48'


def read_data(path):
    value = json.loads(gzip.decompress(Path(path).read_bytes()))
    if value.get('canary') != CANARY:
        raise ValueError('Missing demo canary: ' + str(path))
    return value


def save(path, value):
    path = Path(path)
    payload = gzip.compress(json.dumps({'canary': CANARY, **value},
                                      ensure_ascii=False).encode(), mtime=0)
    temporary = path.with_name(path.name + '.pending')
    with open(temporary, 'xb') as stream:
        os.chmod(temporary, 0o600)
        stream.write(payload)
    temporary.replace(path)


def reasoning_variants(message):
    """Return ({native field: readable text}, opaque) for one assistant message."""
    variants = {key: message[key] for key in ('reasoning', 'reasoning_content')
                if isinstance(message.get(key), str) and message[key].strip()}
    details = message.get('reasoning_details')
    opaque = details is not None and not isinstance(details, list)
    if isinstance(details, list):
        chunks = []
        for block in details:
            if isinstance(block, dict) and block.get('type') == 'reasoning.text' and isinstance(block.get('text'), str):
                chunks.append(block['text'])
            else:
                opaque = True  # Summaries/encrypted blocks are not full traces.
        if ''.join(chunks).strip():
            variants['reasoning_details'] = ''.join(chunks)
    return variants, opaque


def api_json(path, body=None, key=None, base=API):
    """Call an OpenAI-compatible JSON API (OpenRouter by default, or a local vLLM server)."""
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    request = Request(base + path, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(request, timeout=600) as response:
            return json.load(response)
    except HTTPError as error:
        # Do not echo response bodies: an upstream error might contain secrets.
        raise RuntimeError('API HTTP ' + str(error.code) + '; no automatic retry') from None
    except (URLError, TimeoutError, ValueError):
        raise RuntimeError('API response unavailable; no automatic retry') from None


def check_endpoint(profile, required):
    """Verify the pinned model/endpoint live; return (model, endpoint, [prompt, completion] prices)."""
    catalog = api_json('models')['data']
    model = next((m for m in catalog if m['id'] == profile['model']), None)
    endpoints = api_json('models/' + profile['model'] + '/endpoints')['data']['endpoints']
    endpoint = next((e for e in endpoints if e.get('tag') == profile['provider_tag']), None)
    if (model is None or endpoint is None or model.get('canonical_slug') != profile['canonical_slug']
            or endpoint.get('provider_name') != profile['provider_name'] or endpoint.get('status') != 0
            or endpoint.get('quantization') != profile['quantisation']):
        raise ValueError('Pinned model/provider unavailable or changed; no fallback')
    efforts = model.get('reasoning', {}).get('supported_efforts', [])
    if ((efforts is not None and profile['effort'] not in efforts)
            or not set(required).issubset(endpoint.get('supported_parameters', []))
            or (endpoint.get('max_completion_tokens') or profile['max_tokens']) < profile['max_tokens']):
        raise ValueError('Pinned reasoning settings unavailable')
    pricing = endpoint['pricing']
    prices = [float(pricing[k]) for k in ('prompt', 'completion')]
    if any(not math.isfinite(p) or p < 0 for p in prices):
        raise ValueError('Invalid advertised prices')
    # No images/search/server tools are used. Fail if extra charges are advertised.
    if any(float(v) != 0 for k, v in pricing.items()
           if k not in {'prompt', 'completion', 'input_cache_read', 'input_cache_write', 'discount'}):
        raise ValueError('Additional pricing fields need review')
    return model, endpoint, prices


def unpack(path=DATA_DIR):
    """Write a readable `.json` next to each `.json.gz` (one file or a directory).

    Returns `(target, written)` pairs; up-to-date copies are skipped.
    """
    path = Path(path)
    sources = sorted(path.glob('*.json.gz')) if path.is_dir() else [path]
    if not sources:
        raise ValueError('No .json.gz files found')
    results = []
    for source in sources:
        if not source.name.endswith('.json.gz'):
            raise ValueError('Expected a .json.gz file: ' + str(source))
        # Unpacked copies are git-ignored; the gzip file stays the source of truth,
        # so a copy older than its source (e.g. after a pull) is refreshed.
        target = source.with_name(source.name[:-len('.gz')])
        if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
            results.append((target, False))
            continue
        target.write_text(json.dumps(read_data(source), indent=2, ensure_ascii=False) + '\n',
                          encoding='utf-8')
        results.append((target, True))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description='Write readable .json copies of .json.gz files offline.')
    parser.add_argument('path', nargs='?', default=DATA_DIR,
                        help='A .json.gz file or a directory, e.g. a run (default: all datasets)')
    args = parser.parse_args(argv)
    try:
        for target, written in unpack(args.path):
            print(('unpacked: ' if written else 'up to date: ') + str(target))
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
