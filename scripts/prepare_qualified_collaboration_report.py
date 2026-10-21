"""Append stricter identifier summaries to the existing collaboration page."""
import copy
import json
import shutil
from pathlib import Path

from prepare_dashboard_overview import projection
from prepare_dashboard_relationship_summary import text_literal
from prepare_source_relationship_report import category_filter

PAGE = Path('definition/pages/SourceCollaboration')
CARDS = [
    ('orcid-pairs', 'ORCID-qualified researcher pairs', 'ORCID-qualified pairs'),
    ('orcid-publications', 'ORCID-qualified coauthored publications', 'ORCID-qualified publications'),
    ('corroborated-pairs', 'Cross-source corroborated researcher pairs', 'Corroborated pairs'),
    ('corroborated-publications', 'Cross-source corroborated publications', 'Corroborated publications'),
]


def prepare(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError('New candidate folder required')
    before = {f.relative_to(source): f.read_bytes() for f in source.rglob('*') if f.is_file()}
    page = json.loads(before[PAGE / 'page.json'])
    if page['height'] != 1824 or page['width'] != 1920:
        raise ValueError('Reconcile current collaboration layout before extending')
    template = json.loads(before[PAGE / 'visuals/pairs/visual.json'])
    guidance = json.loads(before[PAGE / 'visuals/limits/visual.json'])
    if template['visual']['visualType'] != 'cardVisual':
        raise ValueError('Accepted native card template required')
    shutil.copytree(source, output)
    changed_charts = set()
    for name, kind in [('provider-authors', 'authorship'),
                       ('researcher-pattern', 'coauthorship'),
                       ('institution-pattern', 'institution_cooccurrence')]:
        path = PAGE / 'visuals' / name / 'visual.json'
        chart = json.loads(before[path])
        if chart.get('filterConfig'):
            raise ValueError('Reconcile existing source chart filters')
        relationship_filter = category_filter('RelationshipKind', kind)
        relationship_filter['name'] = 'qualified-collaboration-' + name + '-kind'
        chart['filterConfig'] = {'filters': [relationship_filter]}
        (output / path).write_text(json.dumps(chart, indent=2)+'\n')
        changed_charts.add(path)
    tab = max(json.loads(v)['position']['tabOrder'] for k, v in before.items()
              if k.parent.name != '' and str(k).startswith(str(PAGE / 'visuals')) and k.name == 'visual.json')
    for i, (name, measure, label) in enumerate(CARDS):
        visual = copy.deepcopy(template)
        visual['name'] = name
        visual['position'].update(x=32 + 472*i, y=1840, width=440, height=160,
                                  z=10000+i, tabOrder=tab+1000*(i+1))
        obj = visual['visual']['visualContainerObjects']
        obj['title'][0]['properties']['text'] = text_literal(label)
        obj['general'][0]['properties']['altText'] = text_literal(label)
        obj['visualHeaderTooltip'][0]['properties']['text'] = text_literal(
            'Both researcher keys are checksum-qualified source-stated ORCIDs. '
            'Corroboration requires the same publication and ordered pair in at least two retained providers. '
            'These counts do not authenticate people or establish current employment. Names are display labels only.')
        visual['visual']['query']['queryState']['Data']['projections'] = [
            projection('SourceRelationshipEvidence', measure, measure=True, label=label)]
        path = output / PAGE / 'visuals' / name / 'visual.json'
        if path.exists():
            raise ValueError('Existing visual must not be replaced')
        path.parent.mkdir()
        path.write_text(json.dumps(visual, indent=2)+'\n')
    guidance['name'] = 'qualified-identity-scope'
    guidance['position'].update(x=32, y=2024, width=1856, height=128, z=10005, tabOrder=tab+5000)
    note_style = copy.deepcopy(guidance['visual']['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0].get('textStyle', {}))
    guidance['visual']['objects']['general'][0]['properties']['paragraphs'] = [
        {'textRuns': [{'value': 'Identifier-qualified coauthorship is publication-specific source evidence. '
            'Corroborated counts require the same publication and ORCID pair in two providers; they are a subset, not additional people or publications. '
            'Existing institution pairs remain based on explicit provider/Ringgold identifiers. These summaries do not establish authenticated identity, current employment or institutional agreements.', 'textStyle': note_style}]}]
    guidance['visual']['visualContainerObjects']['general'][0]['properties']['altText'] = text_literal('Qualified identity and corroboration scope')
    path = output / PAGE / 'visuals/qualified-identity-scope/visual.json'
    path.parent.mkdir()
    path.write_text(json.dumps(guidance, indent=2)+'\n')
    page['height'] = 2176
    (output / PAGE / 'page.json').write_text(json.dumps(page, indent=2)+'\n')
    assert all((output / name).read_bytes() == value for name, value in before.items()
               if name != PAGE / 'page.json' and name not in changed_charts), 'Unrelated report content changed'
    return {'preserved_parts': len(before)-4, 'new_visuals': 5, 'changed_existing_parts': 4}
