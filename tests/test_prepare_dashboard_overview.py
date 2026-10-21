"""Preservation and aggregation guards for existing-report presentation preparation."""
import base64
import copy
import json
import unittest
from scripts.prepare_dashboard_overview import prepare, PAGES


def part(path, value):
    return {'path': path, 'payloadType': 'InlineBase64',
            'payload': base64.b64encode(json.dumps(value).encode()).decode()}


def fixture():
    names = [
        ['heading', 'caption', 'pubmed', 'dora', 'overlap', 'footer', 'all-papers'],
        ['activity-groups', 'activity-footer'],
        ['arc-records', 'funding-state', 'funding-candidates', 'funding-confirmed',
         'funding-unclassified', 'funding-note', 'funding-records', 'arc-footer']]
    order = list(PAGES) + ['retained' + str(i) for i in range(6)]
    parts = [part('definition.pbir', {'datasetReference': {'accepted': 'binding'}}),
             part('definition/pages/pages.json', {'pageOrder': order, 'activePageName': 'retained0'})]
    for page, visuals in zip(PAGES, names):
        parts.append(part(f'definition/pages/{page}/page.json', {'name': page, 'height': 1080, 'width': 1920}))
        for i, name in enumerate(visuals):
            parts.append(part(f'definition/pages/{page}/visuals/{name}/visual.json', {
                'name': name, 'position': {'x': 32, 'y': 16, 'width': 350, 'height': 56, 'tabOrder': i},
                'visual': {'visualType': 'textbox', 'query': {'retained': 'query'},
                           'objects': {'general': [{'properties': {'paragraphs': [
                               {'textRuns': [{'value': 'Retained words'}]}]}}]}}}))
    parts.append(part('definition/pages/retained0/page.json', {'complete': 'unrelated content'}))
    return {'definition': {'format': 'PBIR', 'parts': parts}}


class DashboardOverviewTests(unittest.TestCase):
    def test_preserves_original_and_unrelated_parts_and_queries(self):
        source = fixture()
        before = copy.deepcopy(source)
        candidate = prepare(source)
        self.assertEqual(source, before)
        values = {p['path']: p for p in candidate['definition']['parts']}
        for p in source['definition']['parts']:
            if not any(f'/pages/{page}/' in p['path'] for page in PAGES):
                self.assertEqual(values[p['path']], p)
            if '/visuals/' in p['path']:
                old = json.loads(base64.b64decode(p['payload']))
                new = json.loads(base64.b64decode(values[p['path']]['payload']))
                self.assertEqual(old['visual']['query'], new['visual']['query'])
                self.assertEqual(old['position']['tabOrder'], new['position']['tabOrder'])
        self.assertEqual(len(candidate['definition']['parts']), len(source['definition']['parts']) + 10)
        with self.assertRaisesRegex(ValueError, 'Prior overview'):
            prepare(candidate)

    def test_new_cards_use_correct_source_grain_and_guard_format(self):
        candidate = prepare(fixture())
        cards = {p['path'].split('/')[-2]: json.loads(base64.b64decode(p['payload']))
                 for p in candidate['definition']['parts'] if '/visuals/overview-' in p['path']}
        for name, function, column in [('overview-activities', 0, 'ActivityCount'), ('overview-arc', 5, 'SourceID')]:
            card = cards[name]
            self.assertEqual(card['visual']['visualType'], 'cardVisual')
            field = card['visual']['query']['queryState']['Data']['projections'][0]['field']['Aggregation']
            self.assertEqual(field['Function'], function)
            self.assertEqual(field['Expression']['Column']['Property'], column)
            self.assertEqual(card['position']['height'], 97)
        source = fixture()
        source['definition']['format'] = 'PBIR-Legacy'
        with self.assertRaisesRegex(ValueError, 'Current native PBIR'):
            prepare(source)


if __name__ == '__main__':
    unittest.main()
