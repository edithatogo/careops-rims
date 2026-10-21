"""Append evidence-based relationship summaries to PBIR; never change the model."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import urlparse

from prepare_dashboard_overview import literal, projection

PAGE = 'ResearchRelationships'


def text_literal(value):
    return literal("'" + value.replace("'", "''") + "'")


def prepare(source: Path, output: Path, links: dict):
    """Use current native templates; preserve every existing part except page order."""
    if output.exists():
        raise ValueError('Exclusive output required')
    required = {'publications', 'candidate_links', 'confirmed_links'}
    if set(links) != required:
        raise ValueError('Require three qualified existing SharePoint view links')
    for url in links.values():
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or not parsed.hostname or
                not parsed.hostname.endswith('.sharepoint.com') or parsed.username or
                not parsed.path.endswith('.aspx')):
            raise ValueError('Expected an existing HTTPS SharePoint view')
    metadata = json.loads((source/'definition/pages/pages.json').read_text())
    if PAGE in metadata['pageOrder'] or 'ResearchDatasetConsumers' not in metadata['pageOrder']:
        raise ValueError('Fresh report with accepted dataset page required')
    before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    shutil.copytree(source, output)
    base = source/'definition/pages/ReportSection3/visuals'
    def template(name):
        return json.loads((base/name/'visual.json').read_text())
    page = output/'definition/pages'/PAGE
    page.mkdir()
    value = json.loads((source/'definition/pages/ReportSection3/page.json').read_text())
    value.update(name=PAGE, displayName='Research relationships', width=1920,
                 height=1240, displayOption='FitToWidth')
    if 'pageBinding' in value:
        value['pageBinding']['name'] = PAGE+'Binding'
    (page/'page.json').write_text(json.dumps(value, indent=2)+'\n')
    visuals = []
    def add(name, kind, rect, title, help_text, roles=None, words=None, url=None):
        item = template('heading' if kind == 'textbox' else
                        'overview-confirmed' if kind == 'cardVisual' else 'annual-trajectory')
        item['name'] = name
        item['position'] = dict(zip(('x','y','width','height'), rect), z=len(visuals)*100,
                                tabOrder=(20-len(visuals))*1000)
        visual = item['visual']
        visual['visualType'] = kind
        visual.pop('query', None)
        visual.pop('objects', None)
        item.pop('filterConfig', None)
        containers = visual['visualContainerObjects']
        containers['general'] = [{'properties': {'altText': text_literal(title)}}]
        containers['title'] = [{'properties': {'show': literal('true' if kind == 'barChart' else 'false'),
                             'text': text_literal(title), 'fontSize': literal('16D')}}]
        containers['visualHeader'] = [{'properties': {'show': literal('true'),
                                                     'showTooltipButton': literal('true')}}]
        containers['visualHeaderTooltip'] = [{'properties': {'type': text_literal('Default'),
                                                            'text': text_literal(help_text)}}]
        containers['subTitle'] = [{'properties': {'show': literal('false')}}]
        if roles:
            visual['query'] = {'queryState': {r: {'projections': ps} for r, ps in roles.items()}}
        if kind == 'cardVisual':
            visual['objects'] = copy.deepcopy(template('overview-confirmed')['visual']['objects'])
        if words is not None:
            visual['objects'] = {'general': [{'properties': {'paragraphs': [{'textRuns': [{
                'value': words, 'textStyle': {'fontFamily': 'Segoe UI',
                    'fontSize': '24pt' if name == 'relationships-heading' else '14pt',
                    'color': '#172B4D'}}]}]}}]}
        if url:
            visual['visualType'] = 'actionButton'
            visual['objects'] = {
                'text': [{'properties': {'show': literal('true')}},
                         {'selector': {'id': 'default'}, 'properties': {
                             'text': text_literal(title), 'fontSize': literal('14D'),
                             'fontColor': {'solid': {'color': text_literal('#FFFFFF')}},
                             'horizontalAlignment': text_literal('center'),
                             'verticalAlignment': text_literal('middle')}}],
                'fill': [{'properties': {'show': literal('true')}},
                         {'selector': {'id': 'default'}, 'properties': {
                             'fillColor': {'solid': {'color': text_literal('#005A9E')}}}}],
                'icon': [{'properties': {'show': literal('false')}}],
                'outline': [{'properties': {'show': literal('false')}}],
                'shape': [{'properties': {'tileShape': text_literal('rectangle')}}]}
            containers['visualLink'] = [{'properties': {'show': literal('true'),
                'type': text_literal('WebUrl'), 'webUrl': text_literal(url),
                'tooltip': text_literal(help_text)}}]
        folder = page/'visuals'/name
        folder.mkdir(parents=True)
        (folder/'visual.json').write_text(json.dumps(item, indent=2)+'\n')
        visuals.append(name)

    add('relationships-heading', 'textbox', (32,8,1856,64), 'Research relationships',
        'Supported source evidence; no inferred person, project or funding identities.',
        words='RESEARCH RELATIONSHIPS | Evidence and coverage')
    add('relationships-guidance', 'textbox', (32,88,1856,88), 'How to read these summaries',
        'Select a bar to filter related publication and funding evidence; select it again to clear.',
        words='Publication patterns use distinct canonical publications. Author counts and facility matches are source evidence, not verified people or collaboration. Funding candidates remain separate from confirmed reviewed links.')
    for name, measure, x, label, help_text in [
        ('candidates', 'Candidate links', 32, 'Candidate funding links', 'Exact registered publication–ARC award identities awaiting review; not confirmed funding.'),
        ('confirmed', 'Confirmed reviewed links', 504, 'Confirmed reviewed links', 'Only positively admitted, explicitly reviewed confirmed funding links. Zero means no accepted links, not no funding.'),
        ('unresolved', 'Unclassified or unresolved links', 976, 'Unresolved relationship rows', 'Unclassified or unresolved identities remain visible and excluded from confirmed funding.')]:
        add(name, 'cardVisual', (x,200,440,140), label, help_text,
            {'Data': [projection('Funding Relationship Context', measure, measure=True, label=label)]})
    add('source-activities', 'cardVisual', (1448,200,440,140), 'Source activity records',
        'Counts imported source activity keys. Project IDs can repeat; these are not unique verified projects or publication links.',
        {'Data': [projection('DORA Activity Registry', 'DORAActivityKey', function=5,
                             label='Source activity records')]})
    for name, column, x, title, help_text in [
        ('author-pattern', 'AuthorCount', 32, 'Publications by listed author count',
         'Counts distinct publications at each source author count. Multiple authors are a coauthorship signal, not verified collaborators or staff. Unknowns remain blank.'),
        ('facility-pattern', 'FacilityMatchCount', 976, 'Publications by matched facility count',
         'Counts distinct publications at each facility match count. Multiple matches are attribution evidence, not confirmed institutional collaboration. Unknowns remain blank.')]:
        add(name, 'barChart', (x,384,912,360), title, help_text, {
            'Category': [projection('Publication', column)],
            'Y': [projection('Publication', 'Publications', measure=True, label='Distinct publications')]})
    add('relationship-state', 'barChart', (32,784,912,280), 'Funding links by admitted state',
        'Counts relationship rows, not publications or awards. Current register review state determines admission.', {
            'Category': [projection('Funding Relationship Context', 'AdmissionState', label='Admission state')],
            'Y': [projection('Funding Relationship Context', 'Current relationship rows', measure=True, label='Relationship rows')]})
    add('relationship-limits', 'textbox', (976,784,912,152), 'Coverage limits',
        'Project linkage and verified collaboration require authoritative identifiers and evidence.',
        words='Project linkage is not available: no accepted publication–project crosswalk exists. Source project IDs are not assumed unique. Author-label groups remain unresolved identities. No name-based links, combined research total or monetary total is calculated.')
    for i, (key, label, help_text) in enumerate([
        ('publications', 'Open publication register', 'Open the existing keyed source-row register; its row count differs from distinct canonical publications.'),
        ('candidate_links', 'Open candidate funding links', 'Open the existing candidate view for evidence and review; this does not confirm funding.'),
        ('confirmed_links', 'Open confirmed reviewed links', 'Open the existing positively reviewed funding view; an empty view is a valid result.')]):
        add('link-'+key, 'textbox', (976,952+i*72,912,56), label, help_text,
            words=label+' ↗', url=links[key])
    add('relationships-footer', 'textbox', (32,1180,1856,48), 'Evidence boundary',
        'Preserves the current model, source keys, human review and existing access.',
        words='For source records and review, use the existing registers. Model observation time is not provider freshness; labels and missing evidence retain their original uncertainty.')
    metadata['pageOrder'].append(PAGE)
    (output/'definition/pages/pages.json').write_text(json.dumps(metadata, indent=2)+'\n')
    for path, raw in before.items():
        if path != 'definition/pages/pages.json' and (output/path).read_bytes() != raw:
            raise ValueError('Existing part changed: '+path)
    return {'new_page': PAGE, 'new_visuals': len(visuals),
            'existing_parts_preserved_except_page_order': True,
            'source_sha256': hashlib.sha256(b''.join(before.values())).hexdigest()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--links', type=Path, required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.source, a.output, json.loads(a.links.read_text())), indent=2))


if __name__ == '__main__':
    main()
