"""Prepare complete reconciled report inputs for a maintained native template.

Local preparation only; no document generation, service call or native proof.
Selection and identity remain with the existing paired-extraction reconciler.
"""
import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

try:
    from .export_publication_register import assemble_paginated_export
    from .reconcile_full_month_exports import reconcile
except ImportError:
    from export_publication_register import assemble_paginated_export
    from reconcile_full_month_exports import reconcile


def text(value):
    return '' if value is None else str(value)


def prepare(full, monthly, *, template_sha256, output_revision, generated_at):
    context = reconcile(full, monthly)
    if (not isinstance(template_sha256, str) or len(template_sha256) != 64
            or any(c not in '0123456789abcdef' for c in template_sha256)):
        raise ValueError('Exact template SHA256 required')
    if (not isinstance(output_revision, str) or not output_revision.strip()
            or output_revision != output_revision.strip()):
        raise ValueError('Explicit output revision required')
    when = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
    if when.utcoffset() is None:
        raise ValueError('Timezone-aware preparation time required')
    records = assemble_paginated_export(monthly)['records']
    bibliography = []
    for record in records:
        # Include all fields admitted by the existing exact export contract,
        # including nulls, rather than a capped or title-only citation.
        citation = '\n'.join(name + ': ' + json.dumps(value, ensure_ascii=False)
                             for name, value in record.items())
        links = [text(record.get(name)) for name in
                 ('PubMedURL', 'DORAURL', 'EuropePMC_FullTextURL', 'OAUrl')
                 if record.get(name)]
        if record.get('DOI'):
            doi = text(record['DOI'])
            links.append(doi if doi.startswith('https://doi.org/')
                         else 'https://doi.org/' + doi)
        bibliography.append({
            'Citation': citation, 'CanonicalKey': record['CanonicalKey'],
            'SourceURL': '\n'.join(dict.fromkeys(links)),
            'AffiliationEvidence': text(record.get('AttributionEvidence')),
            'DateUncertainty': json.dumps({k: record.get(k) for k in
                ('PublicationDateRaw', 'PublicationDatePrecision',
                 'PublicationMonth')}, ensure_ascii=False),
        })
    fields = {
        'ReportingMonth': context['reporting_month'],
        'ExecutiveSummary': (
            f"{context['monthly_count']} publications in the complete selected month; "
            f"{context['full_count']} in the paired full extraction. "
            f"{context['unknown_month_count']} full-extraction records have no month. "
            + monthly['coverage_note']),
        'AttributionAndFundingContext': (
            'Supplied attribution and funding values are retained in each complete '
            'bibliography record. Missing values remain missing; no assessment is inferred.'),
        'Bibliography': bibliography,
        'SourceAndDateUncertainty': monthly['coverage_note'],
        'DocumentIdentity': 'monthly-publications:' + context['reporting_month'],
        'SourceSnapshotVersion': context['source_snapshot_id'],
        'IncludedCanonicalKeys': json.dumps(
            [r['CanonicalKey'] for r in records], ensure_ascii=False),
        'IncludedRecordCount': str(context['monthly_count']),
        'SourceQueryRefresh': json.dumps(context, ensure_ascii=False, sort_keys=True),
        'TemplateVersion': template_sha256, 'OutputRevision': output_revision,
        'GeneratedAt': generated_at,
    }
    return {
        'format': 'rims-structured-monthly-report-input-v1',
        'status': 'prepared-not-generated', 'fields': fields,
        'reconciliation': context, 'records': copy.deepcopy(records),
        'input_sha256': {name: hashlib.sha256(json.dumps(value, sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            for name, value in [('full', full), ('monthly', monthly)]},
        'native_generation_proved': False,
        'link_rendering_proved': False,
        'generated_at_semantics': 'Input preparation time; not native output creation time',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('full', 'monthly', 'template', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--output-revision', required=True)
    parser.add_argument('--generated-at', required=True)
    args = parser.parse_args()
    result = prepare(json.loads(args.full.read_text()),
        json.loads(args.monthly.read_text()),
        template_sha256=hashlib.sha256(args.template.read_bytes()).hexdigest(),
        output_revision=args.output_revision, generated_at=args.generated_at)
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
