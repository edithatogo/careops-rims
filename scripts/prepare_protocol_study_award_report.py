"""Expose explicit clinical-study chains without implying DORA project coverage."""
import json
import shutil
from pathlib import Path
from prepare_dashboard_overview import literal, projection
from prepare_dashboard_relationship_summary import text_literal
from prepare_source_relationship_report import category_filter

TABLE = 'SourceRelationshipEvidence'
PAGE = Path('definition/pages/SourceStudyAwards')
EXPECTED_STATUS_TEXT = ('Complete publication–project–award chains: not established. A ClinicalTrials.gov study ID is not a DORA project ID. '
                        'An internal study ID or shared researcher/organisation does not establish award funding. '
                        'Source-stated award identifiers remain distinct from existing register awards until a qualified crosswalk exists.')
EXPECTED_STATUS_TOOLTIP = 'No full publication–project–award chain has yet been established.'


def prepare(source, output):
    source, output = Path(source), Path(output)
    page = source / PAGE
    if output.exists() or not (page / 'visuals/award-crosswalk-count/visual.json').is_file():
        raise ValueError('Accepted crosswalk report and exclusive output required')
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    meta = json.loads((page / 'page.json').read_text())
    if meta['height'] != 2400:
        raise ValueError('Accepted source-links page dimensions required')
    status = json.loads((page / 'visuals/chain-status/visual.json').read_text())
    paragraph = status['visual']['objects']['general'][0]['properties']['paragraphs'][0]
    tooltip = status['visual']['visualContainerObjects']['visualHeaderTooltip'][0]['properties']['text']
    if (len(paragraph['textRuns']) != 1 or paragraph['textRuns'][0]['value'] != EXPECTED_STATUS_TEXT
            or tooltip != text_literal(EXPECTED_STATUS_TOOLTIP)):
        raise ValueError('Human-modified chain status requires reconciliation')
    shutil.copytree(source, output)
    meta['height'] = 3000
    (output / PAGE / 'page.json').write_text(json.dumps(meta, indent=2) + '\n')
    status_path = output / PAGE / 'visuals/chain-status/visual.json'
    status = json.loads(status_path.read_text())
    status['visual']['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0]['value'] = (
        'Complete DORA publication–project–award chains: not established. A ClinicalTrials.gov study ID is not a DORA project ID. '
        'The separate clinical-study section below shows chains supported by explicit publication references and versioned protocol funding identifiers. '
        'Source evidence is not reviewed funding approval.')
    status['visual']['visualContainerObjects']['visualHeaderTooltip'][0]['properties']['text'] = text_literal(
        'DORA project chains remain unresolved; clinical-study chains have their own source-supported evidence below.')
    status_path.write_text(json.dumps(status, indent=2) + '\n')
    specs = [
        ('clinical-study-chain-heading', 'award-crosswalk-heading', (32, 2400, 1856, 88), 'Clinical-study funding chains'),
        ('clinical-study-chain-count', 'award-crosswalk-count', (32, 2512, 440, 144), 'Publication–study–award chains'),
        ('clinical-study-award-count', 'award-crosswalk-count', (32, 2680, 440, 144), 'Source study–award links'),
        ('clinical-study-chain-evidence', 'award-crosswalk-evidence', (504, 2512, 1384, 420), 'Explicit clinical-study chains')]
    for index, (name, template, rect, title) in enumerate(specs, 1):
        value = json.loads((page / 'visuals' / template / 'visual.json').read_text())
        value['name'] = name
        value['position'] = dict(zip(('x', 'y', 'width', 'height'), rect), z=3000 + index * 100, tabOrder=110000 + index * 1000)
        visual = value['visual']; visual.pop('query', None); value.pop('filterConfig', None)
        containers = visual['visualContainerObjects']
        containers['general'] = [{'properties': {'altText': text_literal(title)}}]
        containers['title'] = [{'properties': {'show': literal('true' if index == 4 else 'false'), 'text': text_literal(title), 'fontSize': literal('16D')}}]
        containers['visualHeaderTooltip'] = [{'properties': {'type': text_literal('Default'), 'text': text_literal(
            'Explicit trial/protocol/application identifiers and source publication references. Only uniquely mapped publications count as chains. '
            'Versioned source support; not authenticated identity, reviewed funding or DORA project coverage.')}}]
        if index == 1:
            visual['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0]['value'] = (
                'Clinical-study chains use explicit publication → trial references and protocol → grant identifiers. '
                'Only publications mapped uniquely to this register count; other source references remain unmapped. '
                'Protocol versions and evidence are retained. DORA project chains remain unresolved.')
        elif index in (2, 3):
            measure = 'Complete clinical study award chains' if index == 2 else 'Source study award links'
            visual['query'] = {'queryState': {'Data': {'projections': [projection(TABLE, measure, measure=True, label=title)]}}}
        else:
            columns = [('CanonicalKey', 'Publication key'), ('FromKey', 'Clinical study'), ('ToKey', 'Grant URI'),
                       ('SourceVersion', 'Protocol version'), ('SourceURL', 'Protocol evidence')]
            visual['query'] = {'queryState': {'Values': {'projections': [projection(TABLE, col, label=label) for col, label in columns]}}}
            value['filterConfig'] = {'filters': [category_filter('RelationshipKind', 'publication_study_award_chain'), category_filter('AdmissionState', 'Source-supported')]}
            for filt in value['filterConfig']['filters']:
                filt['name'] = name + '-' + filt['name']
        target = output / PAGE / 'visuals' / name / 'visual.json'
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(value, indent=2) + '\n')
    changed = {PAGE / 'page.json', PAGE / 'visuals/chain-status/visual.json'}
    assert all((output / path).read_bytes() == raw for path, raw in before.items() if path not in changed)
    return {'added_visuals': 4, 'existing_visuals_preserved': True, 'existing_text_updated': ['chain-status']}
