"""Bundle clean public source; no private inputs or native operations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def package(output):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT)
    if git('status', '--porcelain', '--untracked-files=all').strip():
        raise ValueError('Commit the reviewed public source before packaging.')
    subprocess.run([sys.executable, str(ROOT / 'scripts/check_public_source.py'), '--staged'], cwd=ROOT, check=True)
    revision = git('rev-parse', 'HEAD').decode().strip()
    output.mkdir(parents=True, exist_ok=False)
    archive = output / 'careops-rims-source.zip'
    subprocess.run(['git', 'archive', '--format=zip', '--output', str(archive.resolve()), revision], cwd=ROOT, check=True)
    receipt = {'sourceCommit': revision, 'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
               'nativeWrites': False, 'publicLicenceGranted': False,
               'scope': 'Current public source only; no native package, activation or acceptance.'}
    (output / 'package.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    package(parser.parse_args().output.resolve())
