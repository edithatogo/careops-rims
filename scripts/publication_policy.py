"""Generic permissive inclusion with evidence-preserving automatic attribution."""
import copy
import hashlib
import json
from pathlib import Path
import re
from scripts.organisation_enrichment import enrich_record, load_reference

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'config/publication-policy.json'


def load_policy(path=POLICY_PATH):
    policy = json.loads(Path(path).read_text())
    return validate_policy(policy)


def validate_policy(policy):
    expected = {'version', 'inclusion', 'retention', 'default_projection', 'uncertain_affiliation',
                'ambiguous_identity', 'source_disappearance', 'corrections_and_retractions',
                'fuzzy_names', 'manual_record_approval'}
    if set(policy) != expected or not isinstance(policy['version'], str) or not policy['version'].strip():
        raise ValueError('Invalid publication policy schema')
    required = {'inclusion': 'all-valid-configured-source-records',
                'retention': 'every-observation-and-version', 'default_projection': 'latest-valid-version',
                'uncertain_affiliation': 'include-with-label', 'ambiguous_identity': 'preserve-separate-source-records',
                'source_disappearance': 'retain-last-good', 'corrections_and_retractions': 'retain-and-label',
                'fuzzy_names': 'candidate-signal-only', 'manual_record_approval': False}
    if any(type(policy[k]) is not type(v) or policy[k] != v for k, v in required.items()):
        raise ValueError('Unsupported policy behaviour; implement changes before selecting them')
    return policy


def notice_flags(record):
    """Read declared notices, including PubMed XML-shaped metadata, not titles."""
    signals = []
    fields = {'publicationnotice', 'publicationtypes', 'publicationtype',
              'publicationtypelist', 'notice', 'reftype', '@reftype'}

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in fields:
                    signals.append(str(child).lower())
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(record)
    metadata = record.get('MetadataJSON')
    if isinstance(metadata, str):
        try:
            visit(json.loads(metadata))
        except (ValueError, TypeError):
            pass  # Original bytes remain retained; never guess from free text.
    flags = []
    if any(record.get(key) is True for key in ('Retraction', 'IsRetracted')) or any('retract' in value for value in signals):
        flags.append('retraction-notice')
    if any(record.get(key) is True for key in ('Correction', 'IsCorrected')) or any('erratum' in value or 'correct' in value for value in signals):
        flags.append('correction-notice')
    return flags


def evaluate(source, source_id, record, *, policy=None, reference=None):
    policy = load_policy() if policy is None else validate_policy(policy)
    if not isinstance(record, dict):
        raise ValueError('Source record must be an object')
    if source not in ('PubMed', 'DORA') or not isinstance(source_id, str) or source_id != source_id.strip() or not source_id:
        raise ValueError('Valid configured source and source identity required')
    if source == 'PubMed' and not re.fullmatch(r'[1-9][0-9]*', source_id):
        raise ValueError('Invalid PubMed identity')
    if source == 'DORA' and (not source_id.startswith('DORA:') or not source_id[5:]):
        raise ValueError('DoRA identity must preserve its namespace')
    key = 'pubmed:' + source_id if source == 'PubMed' else 'dora:' + source_id[5:]
    enriched = enrich_record(copy.deepcopy(record), reference if reference is not None else load_reference())
    matched = enriched.get('OrganisationMatchMethod') == 'explicit-affiliation-alias'
    flags = []
    if not matched:
        flags.append('affiliation-unconfirmed')
    if not record.get('PublicationDateRaw') or record.get('PublicationDatePrecision') not in ('day', 'month', 'year'):
        flags.append('publication-date-uncertain')
    flags.extend(notice_flags(record))
    # Preserve every original field; no employment inference or author-name merge.
    return {'SourceKey': key, 'CanonicalSourceKey': key, 'RegistryDisposition': 'Included',
            'SourceEligibility': 'eligible', 'AffiliationAttribution': 'attributed' if matched else 'undetermined',
            'OrganisationKeys': enriched.get('OrganisationKeys', ''),
            'OrganisationEvidence': enriched.get('OrganisationEvidence', ''),
            'OrganisationReferenceVersion': enriched.get('OrganisationReferenceVersion', ''),
            'UncertaintyFlags': flags, 'PolicyVersion': policy['version'],
            'PolicySHA256': hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
            'IdentityMergeMethod': 'source-identity-only', 'Record': copy.deepcopy(record)}
