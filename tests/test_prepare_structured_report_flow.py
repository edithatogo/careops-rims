import json
import unittest
from scripts.prepare_structured_report_flow import build


class StandardReportFlowTests(unittest.TestCase):
    def build(self, path='/Documents/Reporting/input.json'):
        return build('https://example.sharepoint.com/personal/example_operator', '/Documents/Reporting',
            {'source':'Embedded', 'id':'/providers/Microsoft.PowerApps/apis/shared_sharepointonline',
             'connectionName':'existing','connectionReferenceLogicalName':'rims_existing'}, path)

    def test_cloud_runtime_uses_only_sharepoint_and_builtins_and_no_schedule(self):
        p=self.build()['properties']; d=p['definition']
        self.assertEqual(set(d['triggers']), {'manual'})
        self.assertEqual(d['triggers']['manual']['runtimeConfiguration']['concurrency']['runs'],1)
        self.assertNotIn('shared_wordonlinebusiness',json.dumps(p))
        def visit(actions):
            for action in actions.values():
                self.assertNotEqual(action['type'],'Http')
                if action['type']=='OpenApiConnection':
                    self.assertEqual(action['inputs']['host']['apiId'],
                                     '/providers/Microsoft.PowerApps/apis/shared_sharepointonline')
                if 'actions' in action:visit(action['actions'])
                if 'else' in action:visit(action['else']['actions'])
        visit(d['actions'])

    def test_replay_has_no_writes_and_new_manifest_waits_for_verified_report(self):
        a=self.build()['properties']['definition']['actions'];branches=a['Existing_or_new']
        self.assertEqual(set(branches['actions']),{'Parse_existing','Read_previous_source',
            'Read_previous_report','Guard_unchanged','Replay_result'})
        new=branches['else']['actions']
        self.assertEqual(new['Manifest']['runAfter'],{'Verify_report':['Succeeded']})
        self.assertIn('404',new['Require_missing']['inputs'])
        self.assertIn('201',new['Require_exclusive_folder']['inputs'])
        self.assertIn('Select_bibliography_keys',a['Guard_complete']['inputs'])
        self.assertIn('Read_previous_report',branches['actions']['Guard_unchanged']['inputs'])

    def test_default_input_cannot_escape_reporting_folder(self):
        for path in ['/Documents/Other/input.json','/Documents/Reporting/../input.json',
                     '/Documents/Reporting/input.html']:
            with self.assertRaises(ValueError):self.build(path)
