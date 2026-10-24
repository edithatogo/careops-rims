"""Reject private artefacts, account addresses and deployment identities."""
from pathlib import Path
from contextlib import contextmanager, nullcontext
import argparse
import re
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
BLOCKED = {'.local', 'private', 'downloads', 'data', 'audit', 'reports', '.agents', '.flowagent', '.playwright-cli', 'node_modules'}
SUFFIXES = {'.pbix', '.pbit', '.abf', '.zip', '.bundle', '.msapp', '.msflow', '.docx', '.xlsx', '.pdf', '.pem', '.key', '.pfx', '.p12', '.vsdx'}
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
GUID = re.compile(r'\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b', re.I)
EXAMPLE_HOSTS = {'example.sharepoint.com', 'example-my.sharepoint.com', 'mytenant.sharepoint.com', 'tenant.sharepoint.com', 'contoso.sharepoint.com'}
def inspect(name, raw, mode='100644'):
    path, errors = Path(name), []
    if (any(part.lower() in BLOCKED for part in path.parts) or path.suffix.lower() in SUFFIXES or path.name == '.gitmodules'
        or (path.name.startswith('.env') and path.name not in {'.env.example', '.env.template'})):
        errors.append('private artefact or configuration file')
    if mode in {'120000', '160000'}:
        errors.append('symlink or submodule requires publication review')
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        return errors + ['non-text payload requires publication review']
    if '\x00' in text:
        errors.append('binary payload')
    for address in EMAIL.findall(text):
        domain = address.split('@')[-1].lower()
        if not (domain.endswith(('.invalid', '.example', '.test')) or domain in {'example.com', 'example.org', 'example.net', 'example.gov.au', 'users.noreply.github.com'}):
            errors.append('non-example account address')
    for host in re.findall(r'https?://([^/\s\"<>]+)', text):
        host = host.lower().rstrip("',")
        if 'sharepoint.com' in host and host not in EXAMPLE_HOSTS:
            errors.append('non-example SharePoint target')
    for identity in GUID.findall(text):
        if not (identity.startswith('00000000-0000-4000-8000-') or identity == '00000000-0000-0000-0000-000000000000'):
            errors.append('non-example GUID; use private configuration')
    for account in re.findall(r'/Users/([^/\s\"\'<>]+)', text):
        if account != 'example' and not account.startswith(('{', '(', '[', '$')):
            errors.append('personal filesystem path')
    for account in re.findall(r'/personal/([A-Za-z0-9_]+)', text):
        if account not in {'example_operator', 'dev'}:
            errors.append('personal SharePoint account path')
    return sorted(set(errors))
def read_index_blob(reader, identity):
    """Read one exact raw indexed blob from a persistent Git batch process."""
    reader.stdin.write(identity.encode('ascii') + b'\n')
    reader.stdin.flush()
    header = reader.stdout.readline(256)
    fields = header.split()
    if not header.endswith(b'\n') or len(fields) != 3 or fields[0] != identity.encode('ascii') or fields[1] != b'blob':
        raise ValueError('Invalid indexed blob response')
    size = int(fields[2])
    if size < 0 or size > sys.maxsize:
        raise ValueError('Invalid indexed blob size')
    raw = bytearray()
    remaining = size
    while remaining:
        chunk = reader.stdout.read(min(remaining, 1024 * 1024))
        if not chunk:
            raise ValueError('Incomplete indexed blob response')
        raw.extend(chunk)
        remaining -= len(chunk)
    if reader.stdout.read(1) != b'\n':
        raise ValueError('Incomplete indexed blob response')
    return bytes(raw)

@contextmanager
def index_reader():
    """Stream requested objects without accumulating the repository in memory."""
    command = ['git', 'cat-file', '--batch']
    with subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as reader:
        try:
            yield reader
        finally:
            reader.stdin.close()  # EOF terminates the reader; context closes stdout before wait.
    if reader.returncode != 0:
        raise subprocess.CalledProcessError(reader.returncode, command)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='Inspect exact staged bytes')
    args = parser.parse_args(argv)
    errors = []
    try:
        entries = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=ROOT).split(b'\0')
        with (index_reader() if args.staged else nullcontext(None)) as reader:
            for entry in entries:
                if not entry: continue
                metadata, raw_name = entry.split(b'\t', 1)
                mode, object_id, stage = metadata.decode().split()
                name = raw_name.decode('utf-8')
                if stage != '0':
                    errors.append(name + ': unresolved index conflict')
                    continue
                try:
                    raw = read_index_blob(reader, object_id) if args.staged else (ROOT/name).read_bytes()
                    errors.extend(name + ': ' + reason for reason in inspect(name, raw, mode))
                except (OSError, subprocess.CalledProcessError):
                    errors.append(name + ': unreadable file')
    except (OSError, subprocess.CalledProcessError, ValueError):
        errors.append('Git index or object reader failed; staged content is not verified')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PASS: public-source privacy boundary')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
