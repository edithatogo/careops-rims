"""Keep direct runtime pins and XML entity protection effective in clean installs."""
import importlib.metadata
from pathlib import Path
import re
import unittest


class WorkbookRuntimeTests(unittest.TestCase):
    def test_runtime_input_lock_and_installed_versions_agree(self):
        root = Path(__file__).resolve().parents[1]
        inputs = dict(re.findall(r'^([\w-]+)==([^\s]+)$', (root / 'requirements-runtime.txt').read_text(), re.M))
        locked = dict(re.findall(r'^([\w-]+)==([^\s]+)', (root / 'requirements-runtime.lock').read_text(), re.M))
        self.assertTrue(inputs)
        for name, version in inputs.items():
            self.assertEqual(locked.get(name), version, name)
        for name, version in locked.items():
            self.assertEqual(importlib.metadata.version(name), version, name)

    def test_workbook_xml_reader_rejects_entity_expansion(self):
        from defusedxml.common import EntitiesForbidden
        from openpyxl.xml import DEFUSEDXML
        from openpyxl.xml.functions import fromstring
        self.assertTrue(DEFUSEDXML)
        document = b'<!DOCTYPE x [<!ENTITY expanded "untrusted">]><x>&expanded;</x>'
        with self.assertRaises(EntitiesForbidden):
            fromstring(document)
