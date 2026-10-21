"""Extract identifier evidence from a qualified core-protocol cover table."""
import re


def parse_cover(page_text):
    """Require the maintained identity and funding table, not later co-mentions.

    This is technical source extraction. It conveys no protocol approval,
    scientific judgement, current grant status or authority to conduct a trial.
    """
    page = page_text.split('\f', 1)[0]
    def one(pattern):
        values = re.findall(pattern, page)
        if len(values) != 1:
            raise ValueError('Protocol cover identity/funding field missing or ambiguous')
        return values[0]
    nct = one(r'Clinical trials registration\s+(NCT[0-9]{8})\b')
    protocol = one(r'Protocol number\s+([A-Z]+[0-9]+)\b')
    version = one(r'Protocol version/date\s+(Version [^\n]+)')
    funding_start = page.find('Funding source')
    if funding_start < 0:
        raise ValueError('Explicit funding section required')
    funding = page[funding_start:]
    # Deliberately excludes the adjacent MRFF application and APP-prefixed grant.
    number = one(r'NHMRC 2021 Clinical Trials and Cohort Studies\s+\(Application ID ([0-9]{7})\)')
    if not re.search(r'NHMRC 2021 Clinical Trials and Cohort Studies\s+\(Application ID ' + number + r'\)', funding):
        raise ValueError('Award identifier outside funding section')
    return {'study_identifier': 'clinicaltrials.gov:' + nct,
            'protocol_identifier': protocol,
            'protocol_identifier_namespace': 'clinicaltrials.gov:' + nct + ':org-study-id',
            'protocol_version': version.strip(), 'funder_namespace': 'nhmrc',
            'original_application_id': number,
            'relationship': 'study_award_funding_source', 'source_page': 1}
