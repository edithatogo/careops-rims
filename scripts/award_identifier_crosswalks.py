"""Qualify explicit award aliases without number-only or name-based matching."""
from urllib.parse import urlparse


def qualify_award_alias(award, source_funder_ror, authority, records):
    """Authority is an independently evidenced ROR-to-grant-namespace binding.

    A search result is discovery only. Both the funder namespace and the exact
    original identifier must agree. Prefix variants and duplicate records remain
    unresolved; this function never establishes project funding or human review.
    """
    number = award.get('funder_award_id')
    if not isinstance(number, str) or not number:
        return {'state': 'missing_award_number', 'matches': []}
    if source_funder_ror != authority['ror']:
        return {'state': 'unqualified_funder_namespace', 'matches': []}
    matches = []
    for record in records:
        uri = record.get('purl', '')
        parsed = urlparse(uri)
        expected = '/au-research/grants/' + authority['namespace'] + '/' + number
        if (record.get('type') == 'grant'
                and parsed.scheme == 'https'
                and parsed.netloc == 'purl.org'
                and parsed.path == expected
                and not parsed.query and not parsed.fragment
                and number in record.get('identifiers', [])):
            matches.append({'record_id': str(record['id']), 'award_uri': uri})
    matches.sort(key=lambda row: (row['award_uri'], row['record_id']))
    return {'state': 'source_supported_alias' if len(matches) == 1
            else 'ambiguous_award_identifier' if matches else 'no_exact_identifier',
            'matches': matches}
