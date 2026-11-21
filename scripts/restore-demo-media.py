"""Restore the private team demo's verified MP3 transfer; no credentials."""
import base64
import hashlib
import json
from pathlib import Path
import re

root = Path.cwd()
transfer = root / '.demo-media-transfer'
manifest = json.loads((transfer / 'manifest.json').read_text(encoding='utf-8'))
expected = {item['path']: item for item in manifest['files']}
if len(expected) != 87 or len(expected) != len(manifest['files']):
    raise ValueError('Expected the 87 approved demo clips')
chunks = {path: {} for path in expected}
for part in sorted(transfer.glob('part-*.json')):
    for item in json.loads(part.read_text(encoding='utf-8')):
        path = item['path']
        if path not in expected or item['offset'] in chunks[path]:
            raise ValueError('Unexpected or duplicated transfer chunk')
        chunks[path][item['offset']] = item['content']
proof = []
for path, metadata in expected.items():
    if not re.fullmatch(r'(?:media/(?:demo-samples|story-summaries)/[a-z0-9-]+|public/voice-previews/[A-Za-z0-9]+)\.mp3', path):
        raise ValueError('Unexpected target path')
    offset = 0
    encoded = []
    for start, content in sorted(chunks[path].items()):
        if start != offset:raise ValueError('Missing chunk')
        encoded.append(content);offset += len(content)
    data = base64.b64decode(''.join(encoded), validate=True)
    if len(data) != metadata['bytes'] or hashlib.sha256(data).hexdigest() != metadata['sha256']:
        raise ValueError('MP3 integrity check failed: ' + path)
    if not (data.startswith(b'ID3') or data[:1] == b'\xff'):
        raise ValueError('Not an MP3: ' + path)
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    proof.append({**metadata, 'git_blob_sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()})
(root / 'assets/demo/media-verification.json').write_text(json.dumps({'files': proof}, indent=2) + '\n', encoding='utf-8')
print('Restored and verified', len(proof), 'demo audio files')
