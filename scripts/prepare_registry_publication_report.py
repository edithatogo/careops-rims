"""Keep registry-related publication evidence separate from funding assertions."""
import json
import shutil
from pathlib import Path
from prepare_dashboard_overview import literal, projection
from prepare_dashboard_relationship_summary import text_literal
from prepare_source_relationship_report import category_filter

TABLE = 'SourceRelationshipEvidence'
PAGE = Path('definition/pages/SourceStudyAwards')


def prepare(source, output):
    source, output = Path(source), Path(output)
    page = source / PAGE
    if output.exists() or not (page / 'visuals/clinical-study-chain-count/visual.json').is_file():
        raise ValueError('Accepted clinical-study report and exclusive output required')
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    meta = json.loads((page / 'page.json').read_text())
    if meta['height'] != 3000:
        raise ValueError('Accepted source-links page dimensions required')
    names = ['registry-publication-heading', 'registry-publication-count',
             'registry-reference-count', 'registry-publication-evidence']
    if any((page / 'visuals' / name).exists() for name in names):
        raise ValueError('Existing registry visuals require reconciliation')
    shutil.copytree(source, output)
    meta['height'] = 3600
    (output / PAGE / 'page.json').write_text(json.dumps(meta, indent=2) + '\n')
    specs = [
        ('registry-publication-heading', 'clinical-study-chain-heading', (32, 3000, 1856, 88), 'Grant registry related publications'),
        ('registry-publication-count', 'clinical-study-chain-count', (32, 3112, 440, 144), 'Registry-related publication links'),
        ('registry-reference-count', 'clinical-study-award-count', (32, 3280, 440, 144), 'Registry source publication references'),
        ('registry-publication-evidence', 'clinical-study-chain-evidence', (504, 3112, 1384, 420), 'Explicit registry-related publications')]
    for index, (name, template, rect, title) in enumerate(specs, 1):
        value = json.loads((page / 'visuals' / template / 'visual.json').read_text())
        value['name'] = name
        value['position'] = dict(zip(('x', 'y', 'width', 'height'), rect), z=4000 + index * 100, tabOrder=120000 + index * 1000)
        visual = value['visual']; visual.pop('query', None); value.pop('filterConfig', None)
        containers = visual['visualContainerObjects']
        containers['general'] = [{'properties': {'altText': text_literal(title)}}]
        containers['title'] = [{'properties': {'show': literal('true' if index == 4 else 'false'), 'text': text_literal(title), 'fontSize': literal('16D')}}]
        containers['visualHeaderTooltip'] = [{'properties': {'type': text_literal('Default'), 'text': text_literal(
            'ARDC typed relatedInfo publication references with exact repository handles; publisher DOI identities are used only where explicit. '
            'Source totals include records without an eligible DOI identity. '
            'Related-publication evidence does not establish fundedBy, DORA project membership or reviewed funding.')}}]
        if index == 1:
            visual['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0]['value'] = (
                'Grant registry references use exact repository handles and explicit publisher DOI identities where available. '
                'Only unique publication-register matches count as links; other source references remain retained. '
                'A related-publication reference does not establish fundedBy, DORA project membership or reviewed funding.')
        elif index in (2, 3):
            measure = 'Registry related publication links' if index == 2 else 'Registry source publication references'
            visual['query'] = {'queryState': {'Data': {'projections': [projection(TABLE, measure, measure=True, label=title)]}}}
        else:
            columns = [('CanonicalKey', 'Publication key'), ('PublicationDOI', 'Publisher DOI'), ('ToKey', 'Grant URI'),
                       ('SourceVersion', 'Registry datestamp'), ('SourceURL', 'Registry evidence')]
            visual['query'] = {'queryState': {'Values': {'projections': [projection(TABLE, col, label=label) for col, label in columns]}}}
            value['filterConfig'] = {'filters': [category_filter('RelationshipKind', 'grant_related_publication'), category_filter('AdmissionState', 'Source-supported')]}
            for filt in value['filterConfig']['filters']:
                filt['name'] = name + '-' + filt['name']
        target = output / PAGE / 'visuals' / name / 'visual.json'
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(value, indent=2) + '\n')
    assert all((output / path).read_bytes() == raw for path, raw in before.items() if path != PAGE / 'page.json')
    return {'added_visuals': 4, 'existing_visuals_preserved': True}
