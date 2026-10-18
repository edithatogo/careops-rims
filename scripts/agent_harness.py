"""Small, offline context router and verification runner for a solo repository.

No deployments, evidence certification, Git staging, dependency installation or
private-file bundling. Commands use the active Python interpreter from any cwd.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def public_file(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Context path outside repository: {relative}')
    if any(part in {'private', '.git', '.env', 'downloads'} for part in path.relative_to(root.resolve()).parts):
        raise ValueError(f'Context path is not public: {relative}')
    if not path.is_file():
        raise ValueError(f'Missing context file: {relative}')
    return path


def load_config(root=ROOT):
    config = json.loads((root / 'config/agent-harness.json').read_text())
    if config.get('schema_version') != 1:
        raise ValueError('Unsupported harness schema')
    for name, task in config['tasks'].items():
        if not task.get('test_patterns'):
            raise ValueError(f'Missing test selection: {name}')
        for pattern in task['test_patterns']:
            if '/' in pattern or not pattern.startswith('test_') or not pattern.endswith('.py'):
                raise ValueError(f'Unsafe test pattern: {pattern}')
            if not list((root / 'tests').glob(pattern)):
                raise ValueError(f'Test pattern has no matches: {pattern}')
        for relative in config['baseline'] + task['context']:
            public_file(root, relative)
    return config


def commands(config, task):
    if task == 'all':
        return [[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                [sys.executable, 'scripts/validate_project.py'],
                [sys.executable, 'scripts/webfirst_contracts.py', 'validate'],
                [sys.executable, 'scripts/validate_conductor.py'],
                [sys.executable, 'scripts/powerplatform_tooling.py', 'check']]
    return [[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v']
            for pattern in config['tasks'][task]['test_patterns']]


def run_checks(checks, runner=subprocess.run):
    failed = False
    for command in checks:
        print('RUN:', ' '.join(command), flush=True)
        result = runner(command, cwd=ROOT, check=False)
        failed |= result.returncode != 0
    print('FAIL_LOCAL' if failed else 'PASS_LOCAL_ONLY — live acceptance not evaluated', flush=True)
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['context', 'check', 'doctor'])
    parser.add_argument('--task', default='grants')
    args = parser.parse_args(argv)
    try:
        config = load_config()
        if args.task not in config['tasks'] and not (args.action == 'check' and args.task == 'all'):
            raise ValueError('Unknown task; use grants, publications, organisation, platform or check --task all')
        if args.action == 'doctor':
            print('PASS: public context paths and test selections exist; no tenant checks performed')
            return 0
        if args.action == 'context':
            print('Read in this order. Private runtime evidence must be inspected separately when relevant.')
            for relative in dict.fromkeys(config['baseline'] + config['tasks'][args.task]['context']):
                print(relative)
            print('\nCurrent checkpoint:\n' + public_file(ROOT, 'handoff/CURRENT_STATE.md').read_text())
            return 0
        return run_checks(commands(config, args.task))
    except (ValueError, KeyError, OSError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
