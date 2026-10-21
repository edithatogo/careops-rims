"""Prepare three presentation pages in an existing PBIR definition; no native effects."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import json
import math
from pathlib import Path

PAGES = ('ReportSection3', 'DoraActivityCounts', 'ARCAwardContextReader')
SCHEMA = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json'


def literal(value):
    return {'expr': {'Literal': {'Value': value}}}


def projection(table, column, *, function=None, measure=False, label=None):
    kind = 'Measure' if measure else 'Column'
    field = {kind: {'Expression': {'SourceRef': {'Entity': table}}, 'Property': column}}
    ref = table + '.' + column
    if function is not None:
        field = {'Aggregation': {'Expression': field, 'Function': function}}
        ref = ('Sum' if function == 0 else 'CountNonNull') + '(' + ref + ')'
    return {'field': field, 'queryRef': ref, 'nativeQueryRef': label or column,
            'displayName': label or column}


def prepare(document):
    """Preserve all original files/queries; add aggregate visuals on three pages."""
    result = copy.deepcopy(document)
    definition = result['definition']
    if definition.get('format') != 'PBIR':
        raise ValueError('Current native PBIR required; do not edit a legacy export')
    parts = definition['parts']
    files = {p['path']: p for p in parts}
    if len(files) != len(parts):
        raise ValueError('Duplicate definition part')
    for path in files:
        if Path(path).is_absolute() or '..' in Path(path).parts or '\\' in path:
            raise ValueError('Unsafe definition path')
    order = json.loads(base64.b64decode(files['definition/pages/pages.json']['payload']))
    if len(order['pageOrder']) != 9 or not set(PAGES) <= set(order['pageOrder']):
        raise ValueError('Expected current nine-page report')
    if any('/visuals/overview-' in p for p in files):
        raise ValueError('Prior overview candidate; reconcile before preparing again')

    def read(path):
        return json.loads(base64.b64decode(files[path]['payload'], validate=True))

    def write(path, value):
        if path not in files:
            part = {'path': path, 'payloadType': 'InlineBase64'}
            parts.append(part)
            files[path] = part
        files[path]['payload'] = base64.b64encode(json.dumps(value, ensure_ascii=False, indent=2).encode()).decode()

    def visual_path(page, name):
        return f'definition/pages/{page}/visuals/{name}/visual.json'

    def move(page, name, **rect):
        path = visual_path(page, name)
        value = read(path)
        value['position'].update(rect)
        write(path, value)

    def text(page, name, value):
        path = visual_path(page, name)
        item = read(path)
        paragraphs = item['visual']['objects']['general'][0]['properties']['paragraphs']
        style = copy.deepcopy(paragraphs[0]['textRuns'][0].get('textStyle', {}))
        item['visual']['objects']['general'][0]['properties']['paragraphs'] = [
            {'textRuns': [{'value': value, 'textStyle': style}]}]
        write(path, item)

    def add(page, name, kind, rect, title, roles=None, words=None):
        path = visual_path(page, name)
        if path in files:
            raise ValueError('Existing visual would be replaced')
        tab = max(read(p)['position'].get('tabOrder', 0) for p in files
                  if p.startswith(f'definition/pages/{page}/visuals/')) + 1000
        x, y, width, height = rect
        value = {'$schema': SCHEMA, 'name': name,
                 'position': {'x': x, 'y': y, 'width': width, 'height': height,
                              'z': tab, 'tabOrder': tab},
                 'visual': {'visualType': kind, 'drillFilterOtherVisuals': True}}
        visual = value['visual']
        visual['visualContainerObjects'] = {'title': [{'properties': {
            'show': literal('true' if kind == 'barChart' else 'false'),
            'text': literal("'" + title.replace("'", "''") + "'"),
            'fontSize': literal('15D')}}]}
        if roles:
            visual['query'] = {'queryState': {r: {'projections': ps} for r, ps in roles.items()}}
        if kind == 'barChart':
            visual['query']['sortDefinition'] = {'isDefaultSort': False, 'sort': [
                {'field': copy.deepcopy(roles['Y'][0]['field']), 'direction': 'Descending'}]}
        if words is not None:
            visual['objects'] = {'general': [{'properties': {'paragraphs': [
                {'textRuns': [{'value': words, 'textStyle': {'fontSize': '13pt', 'color': '#475569'}}]}]}}]}
        if kind == 'cardVisual':
            # Compact card sizing is derived from this page's actual canvas height.
            canvas = read(f'definition/pages/{page}/page.json')['height']
            font = min(28, max(12, math.floor(canvas * .028)))
            label = min(14, max(8, math.floor(font * .55)))
            value['position']['height'] = 34 + math.ceil(font * 1.5) + math.ceil(max(label, 12) * 1.5)
            if value['position']['height'] > math.floor(canvas * .15):
                raise ValueError('Canvas too small for compact card')
            visual['objects'] = {k: [{'selector': {'id': 'default'}, 'properties': properties}]
                for k, properties in {
                    'value': {'fontSize': literal(f'{font}D'), 'labelDisplayUnits': literal('1D'), 'labelPrecision': literal('0D')},
                    'label': {'fontSize': literal(f'{label}D')},
                    'padding': {'paddingUniform': literal('8D')},
                    'layout': {'paddingUniform': literal('0D')}}.items()}
            visual['visualContainerObjects']['padding'] = [{'selector': {'id': 'default'}, 'properties': {
                k: literal('8D') for k in ('top', 'bottom', 'left', 'right')}}]
        write(path, value)

    overview, activity, arc = PAGES
    for page, height in [(overview, 1488), (activity, 1488), (arc, 1502)]:
        path = f'definition/pages/{page}/page.json'
        data = read(path)
        data['height'] = height
        write(path, data)
    text(overview, 'heading', 'RIMS | Research overview')
    move(overview, 'heading', y=8, height=52)
    text(overview, 'caption', 'Publication filters apply to publication charts. Activity and ARC source-context cards have separate populations; these are not a combined research total.')
    for name, x in [('pubmed', 32), ('dora', 504), ('overlap', 976)]:
        move(overview, name, x=x, y=1120, width=440, height=96)
    move(overview, 'footer', x=32, y=1400, width=1856, height=64)
    entries = [
        ('activities', 'Retained source activities', (504, 112, 440, 97), projection('DoraActivityCounts', 'ActivityCount', function=0, label='Source activities')),
        ('arc', 'ARC source records (not funded total)', (976, 112, 440, 97), projection('ARCAwardContext', 'SourceID', function=5, label='ARC source records')),
        ('confirmed', 'Confirmed reviewed funding links', (1448, 112, 440, 97), projection('Funding Relationship Context', 'Confirmed reviewed links', measure=True)),
        ('candidates', 'Candidate funding links', (1448, 1120, 440, 97), projection('Funding Relationship Context', 'Candidate links', measure=True)),
        ('unknown-month', 'Publications without usable month', (32, 960, 440, 97), projection('Publication', 'Publications Without Usable Month', measure=True, label='Without usable month'))]
    for name, title, rect, field in entries:
        add(overview, 'overview-' + name, 'cardVisual', rect, title, {'Data': [field]})
    add(overview, 'overview-scope', 'textbox', (504, 960, 1384, 120), '', words='Activity and ARC source context is independent of publication year, source and facility filters. Source labels and statuses remain as supplied. Candidate funding relationships and confirmed reviewed links remain separate.')
    add(overview, 'overview-coverage', 'textbox', (32, 1240, 1856, 140), '', words='Model coverage: retained publication, activity and ARC populations. Studies and NHMRC/MRFF award registers are not connected to this model. Acquisition dates differ by source; a model processing timestamp is not provider freshness. No combined research population or cross-source monetary total is implied.')
    move(activity, 'activity-groups', x=32, y=990, width=1856, height=360)
    move(activity, 'activity-footer', x=32, y=1370, width=1856, height=100)
    for name, column, title, x, width in [('sites', 'SiteName', 'Activities by retained site label', 32, 912), ('diseases', 'DiseaseCategory', 'Activities by disease category (including unknown)', 960, 928)]:
        add(activity, 'overview-' + name, 'barChart', (x, 608, width, 350), title, {
            'Category': [projection('DoraActivityCounts', column)],
            'Y': [projection('DoraActivityCounts', 'ActivityCount', function=0, label='Activities')]})
    move(arc, 'arc-records', x=32, y=710, width=1856, height=300)
    for name in ('funding-state', 'funding-candidates', 'funding-confirmed', 'funding-unclassified', 'funding-note'):
        move(arc, name, y=1030)
    move(arc, 'funding-records', x=32, y=1126, width=1856, height=260)
    move(arc, 'arc-footer', x=32, y=1402, width=1856, height=84)
    add(arc, 'overview-award-status', 'barChart', (32, 390, 1856, 300), 'ARC source records by source status (not confirmed funding)', {
        'Category': [projection('ARCAwardContext', 'Status')],
        'Y': [projection('ARCAwardContext', 'SourceID', function=5, label='ARC source records')]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--definition', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.definition.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
        raise ValueError('Native preimage hash mismatch')
    candidate = prepare(json.loads(raw))
    with args.output.open('x') as stream:
        json.dump(candidate, stream, indent=2)
    print('Prepared three pages; model and six other pages preserved; native verification pending')


if __name__ == '__main__':
    main()
