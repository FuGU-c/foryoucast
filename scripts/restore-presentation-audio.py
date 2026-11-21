"""Materialize the user-requested narration upload from verified transfer parts."""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

def digest(data):return hashlib.sha256(data).hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path.cwd());args=parser.parse_args()
 root=args.root.resolve();transfer=root/'.audio-transfer';out=root/'presentation-audio';out.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((transfer/'manifest.json').read_text(encoding='utf-8'))
 allowed={'seranews-presentation-voice-pack.zip','seranews-presentation-voice-150s.wav'}
 for artifact in manifest['artifacts']:
  if artifact['name'] not in allowed or not 0<artifact['bytes']<50_000_000:raise ValueError('Unexpected artifact')
  chunks=[]
  for name in artifact['parts']:
   if not re.fullmatch(r'(?:pack|wav)-\d{3}\.b64',name):raise ValueError('Unexpected transfer part')
   chunks.append((transfer/name).read_text(encoding='ascii'))
  data=base64.b64decode(''.join(chunks),validate=True)
  if artifact['encoding']=='gzip-base64':
   with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:data=compressed.read(artifact['bytes']+1)
  elif artifact['encoding']!='base64':raise ValueError('Unknown encoding')
  if len(data)!=artifact['bytes'] or digest(data)!=artifact['sha256']:raise ValueError('Artifact integrity check failed')
  (out/artifact['name']).write_bytes(data)
 with zipfile.ZipFile(out/'seranews-presentation-voice-pack.zip') as archive:
  for item in archive.infolist():
   if not re.fullmatch(r'(?:README\.md|timing\.json|seranews-presentation-voice-150s\.mp3|scene_clips/scene-\d{2}-\d{3}s\.mp3)',item.filename):raise ValueError('Unexpected archive path')
   if item.file_size>20_000_000:raise ValueError('Unexpected archive entry size')
   data=archive.read(item)
   target=out/item.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 proof=[]
 for file in sorted(out.rglob('*')):
  if file.is_file() and file.name!='UPLOAD-VERIFIED.json':
   data=file.read_bytes();proof.append({'path':file.relative_to(out).as_posix(),'bytes':len(data),'sha256':digest(data),
    'git_blob_sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()})
 (out/'UPLOAD-VERIFIED.json').write_text(json.dumps({'voice':'Marty — Warm, Confident Narrator','duration_seconds':150,
  'silent_window':[87,94],'files':proof},indent=2),encoding='utf-8')
 print(f'Restored and verified {len(proof)} narration files.')

if __name__=='__main__':main()

