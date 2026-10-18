"""Execute the real package/privacy guards in an isolated source repository."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class ReleaseCandidateTests(unittest.TestCase):
    def test_actual_archive_identity_replay_dirty_and_private_source_refusals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'scripts').mkdir()
            for name in ['build_release_candidate.py', 'check_public_source.py']:
                shutil.copyfile(ROOT / 'scripts' / name, root / 'scripts' / name)
            (root / 'README.md').write_text('Fictional source fixture\n')
            (root / '.gitignore').write_text('.local/\n')
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args])
            def commit():
                git('add', '.')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Fictional source')
            git('init', '-q'); commit()
            command = [sys.executable, str(root / 'scripts/build_release_candidate.py'), '--output']
            def run(name):
                return subprocess.run(command + [str(root / '.local' / name)], cwd=root, capture_output=True)
            result = run('one'); self.assertEqual(result.returncode, 0, result.stderr)
            result = run('two'); self.assertEqual(result.returncode, 0, result.stderr)
            output = root / '.local/one'; archive = output / 'careops-rims-source.zip'
            receipt = json.loads((output / 'package.json').read_text())
            self.assertEqual(receipt['archiveSha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(receipt['sourceCommit'], git('rev-parse', 'HEAD').decode().strip())
            self.assertEqual(archive.read_bytes(), (root / '.local/two/careops-rims-source.zip').read_bytes())
            self.assertFalse(receipt['nativeWrites']); self.assertFalse(receipt['publicLicenceGranted'])
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(bundle.read('README.md'), (root / 'README.md').read_bytes())
                self.assertFalse(any(name.startswith(('.git/', '.local/')) for name in bundle.namelist()))
            self.assertNotEqual(run('one').returncode, 0)
            self.assertEqual(receipt['archiveSha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            (root / 'README.md').write_text('Unreviewed edit\n')
            self.assertNotEqual(run('dirty').returncode, 0)
            commit()
            private = root / 'private'; private.mkdir(); (private / 'receipt.json').write_text('{}')
            commit()
            self.assertNotEqual(run('private').returncode, 0)
            self.assertFalse((root / '.local/private').exists())
