"""Outbound-only, signed n8n requests. Provider keys stay in n8n credentials."""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'radar', 'script', 'news', 'audio'}


class CloudError(RuntimeError):
    def __init__(self, message, *, retryable=False, uncertain=False, retry_after=30):
        super().__init__(message)
        self.retryable, self.uncertain, self.retry_after = retryable, uncertain, retry_after


def connection(root=ROOT):
    try:
        result = json.loads((Path(root) / 'data' / 'cloud-connection.json').read_text(encoding='utf-8'))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def ensure_key(root=ROOT):
    folder = Path(root) / '.secrets'
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / 'n8n-signing.pem'
    if not path.exists():
        key = Ed25519PrivateKey.generate()
        value = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        with path.open('xb') as target:
            target.write(value)
        if os.name != 'nt':
            path.chmod(0o600)
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def public_key(root=ROOT):
    return ensure_key(root).public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def signed_body(kind, payload, root=ROOT, request_id=None):
    if kind not in KINDS:
        raise ValueError('Unknown workflow operation')
    message = json.dumps({'id': request_id or uuid.uuid4().hex, 'iat': int(time.time()), 'kind': kind, 'payload': payload}, ensure_ascii=False, separators=(',', ':'))
    return {'message': message, 'signature': base64.b64encode(ensure_key(root).sign(message.encode())).decode()}


def invoke(kind, payload, *, root=ROOT, request_id=None, timeout=90):
    config = connection(root)
    url = config.get('webhooks', {}).get(kind)
    parts = urlsplit(url or '')
    if parts.scheme != 'https' or not parts.hostname or not parts.hostname.endswith('.app.n8n.cloud') or parts.username or parts.password:
        raise CloudError('This cloud workflow is not configured.')
    data = json.dumps(signed_body(kind, payload, root, request_id)).encode()
    if len(data) > 2_000_000:
        raise CloudError('This preparation batch is too large; split it into smaller batches.')
    request = Request(url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'Seranews-Demo/1.0'}, method='POST')
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(22_000_001)
        if len(raw) > 22_000_000:
            raise CloudError('The cloud audio response exceeded the chapter limit.')
        value = json.loads(raw)
    except HTTPError as exc:
        if exc.code == 429:
            message = 'The voice service is busy. Preparing Basic audio first.' if kind == 'audio' else 'The writing provider is busy. Reviewed summaries remain available.'
            raise CloudError(message, retryable=True, retry_after=45) from None
        raise CloudError(f'The cloud workflow returned HTTP {exc.code}. Check its n8n execution.', uncertain=kind == 'audio' and exc.code >= 500) from None
    except (URLError, TimeoutError, OSError):
        raise CloudError('The cloud request did not finish. Saved work is kept.', retryable=kind != 'audio', uncertain=kind == 'audio') from None
    except ValueError:
        raise CloudError('The cloud workflow returned an invalid response.') from None
    if not isinstance(value, dict):
        raise CloudError('The cloud workflow returned an unexpected response.')
    if not value.get('ok'):
        raise CloudError(str(value.get('error', 'Cloud processing failed.'))[:240], retryable=value.get('error_code') == 'provider_queue', uncertain=bool(value.get('uncertain')), retry_after=min(180, max(10, int(value.get('retry_after') or 30))))
    return value


def capabilities(root=ROOT):
    config = connection(root)
    return {'generation': True, 'n8n': bool(config.get('verified_at')), 'elevenlabs': bool(config.get('audio_ready')), 'ai': bool(config.get('ai_ready')), 'mode': 'n8n-connected' if config.get('verified_at') else 'local-audio', 'workflows': config.get('workflow_links', {})}
