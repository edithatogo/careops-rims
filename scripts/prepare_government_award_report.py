"""Expose historical government-record references while preserving existing visuals."""
import json
import shutil
from pathlib import Path

from prepare_dashboard_overview import literal, projection
from prepare_dashboard_relationship_summary import text_literal
from prepare_source_relationship_report import category_filter

PAGE = Path('definition/pages/SourceStudyAwards')
TABLE = 'SourceRelationshipEvidence'
EXPLANATION = ('Explicit Crossref funding numbers match exact application IDs in retained historical NHMRC outcomes. '
               'These links identify historical source records. They do not establish current award status, '
               'DORA project membership or reviewed funding; existing register totals are unchanged.')


def prepare(source, output):
    source, output = Path(source), Path(output)
    page = source / PAGE
    if output.exists() or not (page / 'visuals/registry-publication-evidence/visual.json').is_file():
        raise ValueError('Accepted registry report and exclusive output required')
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    meta = json.loads((page / 'page.json').read_text())
    if meta['height'] != 3600:
        raise ValueError('Accepted registry page dimensions required')
    specs = [
        ('government-award-heading', 'registry-publication-heading', (32, 3600, 1856, 88), 'Historical government application references'),
        ('government-publication-count', 'registry-publication-count', (32, 3712, 440, 144), 'Government-record publication links'),
        ('government-source-count', 'registry-reference-count', (32, 3880, 440, 144), 'Government source award references'),
        ('government-award-evidence', 'registry-publication-evidence', (504, 3712, 1384, 420), 'Exact historical application references')]
    if any((page / 'visuals' / name).exists() for name, *_ in specs):
        raise ValueError('Existing government visuals require reconciliation')
    shutil.copytree(source, output)
    meta['height'] = 4200
    (output / PAGE / 'page.json').write_text(json.dumps(meta, indent=2) + '\n')
    for index, (name, template, rect, title) in enumerate(specs, 1):
        value = json.loads((page / 'visuals' / template / 'visual.json').read_text())
        value['name'] = name
        value['position'] = dict(zip(('x', 'y', 'width', 'height'), rect),
                                 z=5000 + index * 100, tabOrder=130000 + index * 1000)
        visual = value['visual']
        visual.pop('query', None)
        value.pop('filterConfig', None)
        containers = visual['visualContainerObjects']
        containers['general'] = [{'properties': {'altText': text_literal(title + '. ' + EXPLANATION)}}]
        containers['title'] = [{'properties': {'show': literal('true' if index == 4 else 'false'),
                                              'text': text_literal(title), 'fontSize': literal('16D')}}]
        containers['visualHeaderTooltip'] = [{'properties': {'type': text_literal('Default'),
                                                           'text': text_literal(EXPLANATION)}}]
        if index == 1:
            visual['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0]['value'] = EXPLANATION
        elif index in (2, 3):
            measure = 'Government record publication links' if index == 2 else 'Government source award references'
            visual['query'] = {'queryState': {'Data': {'projections': [projection(TABLE, measure, measure=True, label=title)]}}}
        else:
            columns = [('CanonicalKey', 'Publication key'), ('PublicationDOI', 'Publication DOI'),
                       ('ToKey', 'Historical application key'), ('ToLabel', 'Original application ID'),
                       ('SourceURL', 'Publication funding evidence')]
            visual['query'] = {'queryState': {'Values': {'projections': [projection(TABLE, col, label=label) for col, label in columns]}}}
            value['filterConfig'] = {'filters': [category_filter('RelationshipKind', 'publication_government_award_reference'),
                                                 category_filter('AdmissionState', 'Source-supported')]}
            for filt in value['filterConfig']['filters']:
                filt['name'] = name + '-' + filt['name']
        target = output / PAGE / 'visuals' / name / 'visual.json'
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(value, indent=2) + '\n')
    assert all((output / path).read_bytes() == raw for path, raw in before.items() if path != PAGE / 'page.json')
    return {'added_visuals': 4, 'existing_visuals_preserved': True}
