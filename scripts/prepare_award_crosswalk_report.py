"""Append exact award-crosswalk evidence to the existing source links page."""
import copy
import json
import shutil
from pathlib import Path
from prepare_dashboard_overview import projection, literal
from prepare_dashboard_relationship_summary import text_literal
from prepare_source_relationship_report import category_filter

TABLE = 'SourceRelationshipEvidence'


def prepare(source, output):
    source = Path(source); output = Path(output)
    page_path = Path('definition/pages/SourceStudyAwards')
    page = source / page_path
    if not page.is_dir() or output.exists():
        raise ValueError('Existing source-link page and exclusive output required')
    if (page / 'visuals/award-crosswalk-evidence').exists():
        raise ValueError('Existing crosswalk presentation requires reconciliation')
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    shutil.copytree(source, output)
    meta = json.loads((output / page_path / 'page.json').read_text())
    if meta['height'] != 1856:
        raise ValueError('Qualified source-link page height required')
    meta['height'] = 2400
    (output / page_path / 'page.json').write_text(json.dumps(meta, indent=2) + '\n')
    configs = [
        ('award-crosswalk-heading', 'guidance', (32, 1832, 1856, 64), 'Exact award identifier crosswalks'),
        ('award-crosswalk-count', 'grant-refs', (32, 1920, 440, 144), 'Mapped publication–award links'),
        ('award-crosswalk-evidence', 'source-grant-references', (504, 1920, 1384, 420), 'Source-supported grant identifier mappings')]
    for i, (name, template, rect, title) in enumerate(configs, 1):
        v = json.loads((page / 'visuals' / template / 'visual.json').read_text())
        v['name'] = name
        v['position'] = dict(zip(('x', 'y', 'width', 'height'), rect), z=(20 + i) * 100, tabOrder=100000 + i * 1000)
        a = v['visual']; a.pop('query', None); v.pop('filterConfig', None)
        c = a['visualContainerObjects']
        c['general'] = [{'properties': {'altText': text_literal(title)}}]
        c['title'] = [{'properties': {'show': literal('true' if i == 3 else 'false'), 'text': text_literal(title), 'fontSize': literal('16D')}}]
        c['visualHeaderTooltip'] = [{'properties': {'type': text_literal('Default'), 'text': text_literal('Exact source funder identifiers and original grant numbers; source-supported, not reviewed funding. Duplicate source assertions are counted once per canonical publication and grant URI.')}}]
        if i == 1:
            a['objects'] = {'general': [{'properties': {'paragraphs': [{'textRuns': [{'value': 'Exact identifiers connect source assertions to grant URIs. These links do not merge award-register rows, establish project funding or complete a publication–project–award chain.', 'textStyle': {'fontFamily': 'Segoe UI', 'fontSize': '14pt', 'color': '#172B4D'}}]}]}}]}
        elif i == 2:
            a['query'] = {'queryState': {'Data': {'projections': [projection(TABLE, 'Mapped publication award links', measure=True, label=title)]}}}
        else:
            a['query'] = {'queryState': {'Values': {'projections': [projection(TABLE, col, label=label) for col, label in [('CanonicalKey', 'Publication key'), ('ToKey', 'Grant URI'), ('SourceProvider', 'Assertion source'), ('SourceURL', 'Source evidence'), ('ObservedUTC', 'Observed UTC')]]}}}
            kinds = category_filter('RelationshipKind', 'award_identifier_alias')
            kinds['filter']['Where'][0]['Condition']['In']['Values'].append([{'Literal': {'Value': "'publication_award_crosswalk'"}}])
            v['filterConfig'] = {'filters': [kinds, category_filter('AdmissionState', 'Source-supported')]}
            for f in v['filterConfig']['filters']:
                f['name'] = name + '-' + f['name']
        target = output / page_path / 'visuals' / name
        target.mkdir(parents=True)
        (target / 'visual.json').write_text(json.dumps(v, indent=2) + '\n')
    assert all((output / path).read_bytes() == raw for path, raw in before.items() if path != page_path / 'page.json')
    return {'added_visuals': 3, 'existing_visuals_preserved': True}
