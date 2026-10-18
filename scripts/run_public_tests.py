"""Run tenant-free regression tests; print explicit private-workspace exclusions."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    'test_agent_harness': 'private checkpoint/context required by the historical harness',
    'test_grants_pages': 'excluded native model audit snapshot',
    'test_powerquery_schema': 'excluded native model audit snapshot',
    'test_project': 'excluded source/model audit snapshots',
    'test_webfirst': 'private acceptance manifests and excluded review records',
}
def deny_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise RuntimeError('Public tests must not access the network')
def main():
    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tests'))
    sys.addaudithook(deny_network)
    suite = unittest.TestSuite(); loader = unittest.TestLoader()
    modules = sorted(p.stem for p in (ROOT / 'tests').glob('test_*.py'))
    for name in EXCLUDED:
        if name not in modules: raise RuntimeError('Stale public-suite exclusion: ' + name)
        print('EXCLUDED ' + name + ': ' + EXCLUDED[name], flush=True)
    for name in modules:
        if name not in EXCLUDED: suite.addTests(loader.loadTestsFromName(name))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1
if __name__ == '__main__': raise SystemExit(main())
