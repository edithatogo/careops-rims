"""Check relative Markdown file links in the public source (offline)."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit
ROOT = Path(__file__).resolve().parents[1]
def main():
    errors = []
    for name in subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'):
        if not name.endswith('.md'): continue
        p = ROOT / name
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', p.read_text()):
            target = target.split('#')[0].strip('<>')
            if not target or urlsplit(target).scheme: continue
            q = ROOT / target.lstrip('/') if target.startswith('/') else p.parent / unquote(target)
            if not q.exists(): errors.append(name + ': ' + target)
    if errors: print('\n'.join(errors)); return 1
    print('PASS: public Markdown file links'); return 0
if __name__ == '__main__': raise SystemExit(main())
