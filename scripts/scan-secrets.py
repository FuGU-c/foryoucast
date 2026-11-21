"""Run pinned Gitleaks with verified release bytes and fully redacted output."""
import argparse
import hashlib
import io
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

VERSION='8.30.1'
ROOT=Path(__file__).resolve().parents[1]

def download(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Seranews-Secret-Audit'})
    with urllib.request.urlopen(request,timeout=90) as response:return response.read()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    system=platform.system().lower()
    if system not in ('windows','linux','darwin'):parser.error('Unsupported OS')
    architecture='arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x64'
    extension='zip' if system=='windows' else 'tar.gz'
    name=f'gitleaks_{VERSION}_{system}_{architecture}.{extension}'
    base=f'https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/'
    checks=download(base+f'gitleaks_{VERSION}_checksums.txt').decode()
    expected=next(line.split()[0] for line in checks.splitlines() if line.split()[-1]==name)
    archive=download(base+name)
    if hashlib.sha256(archive).hexdigest()!=expected:raise RuntimeError('Scanner checksum verification failed')
    with tempfile.TemporaryDirectory(prefix='seranews-secret-scan-') as temp:
        executable=Path(temp)/('gitleaks.exe' if system=='windows' else 'gitleaks')
        if extension=='zip':
            with zipfile.ZipFile(io.BytesIO(archive)) as package:data=package.read('gitleaks.exe')
        else:
            with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as package:data=package.extractfile('gitleaks').read()
        executable.write_bytes(data);executable.chmod(0o700)
        command=[str(executable),'git',str(args.source.resolve()),'--log-opts=--all','--config='+str(ROOT/'.gitleaks.toml'),'--redact=100','--no-banner']
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            command+=['--report-format=json','--report-path='+str(args.report.resolve())]
        return subprocess.run(command,check=False).returncode

if __name__=='__main__':raise SystemExit(main())
