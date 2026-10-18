"""Validate Conductor structure, local links, dependencies and completion state."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def validate(root=ROOT):
    errors = []
    base = root / 'conductor'
    for name in ['index.md', 'product.md', 'product-guidelines.md', 'tech-stack.md', 'workflow.md', 'tracks.md', 'code_styleguides/general.md']:
        if not (base / name).is_file():
            errors.append('Missing conductor/' + name)
    tracks = {}
    archived_ids = set()
    for collection in (base / 'tracks', base / 'archive'):
        if not collection.is_dir():
            continue
        for folder in sorted(collection.iterdir()):
            if not folder.is_dir() or folder.name == 'index.md':
                continue
            archived = collection.name == 'archive'
            if archived:
                archived_ids.add(folder.name)
            required = ['index.md', 'spec.md', 'plan.md', 'metadata.json']
            for name in required:
                if not (folder / name).is_file():
                    errors.append(f'Missing {folder}/{name}')
            try:
                metadata = json.loads((folder / 'metadata.json').read_text())
            except (ValueError, OSError) as exc:
                errors.append(f'{folder.name}: invalid metadata: {exc}')
                continue
            tracks[folder.name] = metadata
            if metadata.get('id', metadata.get('track_id')) != folder.name:
                errors.append(f'{folder.name}: metadata identity mismatch')
            if metadata.get('status') in {'complete', 'completed'} and (folder / 'plan.md').is_file():
                if re.search(r'^\s*- \[ \]', (folder / 'plan.md').read_text(), re.M):
                    errors.append(f'{folder.name}: complete with unfinished tasks')
    register = (base / 'tracks.md').read_text()
    for name, meta in tracks.items():
        if name not in archived_ids and f'tracks/{name}/' not in register:
            errors.append(f'{name}: absent from track register')
        for dep in meta.get('depends_on', []):
            if dep not in tracks:
                errors.append(f'{name}: missing dependency {dep}')
    visited, active = set(), set()
    def visit(name):
        if name in active:
            errors.append(f'Dependency cycle at {name}')
            return
        if name in visited or name not in tracks:
            return
        active.add(name)
        for dep in tracks[name].get('depends_on', []):
            visit(dep)
        active.remove(name)
        visited.add(name)
    for name in tracks:
        visit(name)
    for path in base.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if '://' in link or link.startswith('#'):
                continue
            target = link.split('#')[0]
            if target and not (path.parent / target).exists():
                errors.append(f'{path.relative_to(root)}: broken link {target}')
    return errors


if __name__ == '__main__':
    problems = validate()
    for problem in problems:
        print('FAIL:', problem)
    print(f'Conductor: {len(problems)} errors; structure only, live acceptance not evaluated')
    raise SystemExit(bool(problems))
