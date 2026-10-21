"""Compile exact-byte contracts for the three accepted NHMRC source packets.

All payload literals belong in private definition artifacts. The emitted reader
compares complete actual bytes, not mutable manifest hashes or lengths alone.
External batch/rule pins are required independently of each packet's contents.
"""
import base64
import copy
import hashlib
import json
import re
import zlib
from pathlib import Path
from urllib.parse import urlparse

PATH = 'definition/tables/SourceRelationshipEvidence.tmdl'
PROJECTORS = ('GNTProjector', 'APPProjector', 'RemainingAPPProjector')


def nonempty(value):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError('Explicit nonblank unpadded string identity required')
    return value


def deflate(raw):
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(compressor.compress(raw) + compressor.flush()).decode()


def packet_contract(folder, archive_url, *, expected_batch, expected_rule_sha256):
    expected_batch, expected_rule_sha256 = nonempty(expected_batch), nonempty(expected_rule_sha256)
    archive_url = nonempty(archive_url)
    url = urlparse(archive_url)
    if (not re.fullmatch(r'[0-9a-f-]{36}', expected_batch)
            or not re.fullmatch(r'[0-9a-f]{64}', expected_rule_sha256)
            or url.scheme != 'https' or not (url.hostname or '').endswith('.sharepoint.com')
            or url.netloc != url.hostname or url.query or url.fragment
            or '/Documents/' not in url.path
            or archive_url.split('/')[-1] != 'award-crosswalk-' + expected_batch):
        raise ValueError('Exact private archive URL and independent batch/rule pins required')
    folder = Path(folder)
    manifest_raw = (folder / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    rule_raw = (folder / 'rule-authority.json').read_bytes()
    if hashlib.sha256(rule_raw).hexdigest() != expected_rule_sha256:
        raise ValueError('Independent rule digest differs from actual bytes')
    rule = json.loads(rule_raw)
    if manifest.get('batch') != expected_batch or manifest.get('complete') is not True:
        raise ValueError('Independent packet batch/complete contract failed')
    entries, sources = {}, {}
    for entry in manifest['files']:
        name = nonempty(entry['name'])
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) or name in entries:
            raise ValueError('Unsafe or repeated packet filename')
        entries[name] = entry
    for source in rule['source_files']:
        name = nonempty(source['name'])
        if name in sources:
            raise ValueError('Repeated rule source')
        sources[name] = source
    if set(entries) != set(sources) | {'rule-authority.json'}:
        raise ValueError('Manifest/rule file coverage differs')
    contract = {}
    for name, entry in entries.items():
        raw = (folder / name).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        pin = entry if name == 'rule-authority.json' else sources[name]
        if (entry['sha256'] != sha or pin['sha256'] != sha
                or type(entry['bytes']) is not int or entry['bytes'] != len(raw)
                or pin['bytes'] != len(raw)):
            raise ValueError('Actual source bytes fail independent policy pins')
        contract[archive_url + '/' + name] = {'sha256': sha, 'bytes': len(raw), 'payload': deflate(raw)}
    contract[archive_url + '/manifest.json'] = {
        'sha256': hashlib.sha256(manifest_raw).hexdigest(), 'bytes': len(manifest_raw),
        'payload': deflate(manifest_raw)}
    return contract


def verify_payload(contract, url, actual):
    entry = contract[url]
    expected = zlib.decompress(base64.b64decode(entry['payload'], validate=True), -15)
    if expected != actual or len(actual) != entry['bytes']:
        raise ValueError('Actual source bytes differ from independently pinned contract')
    return actual


def mtext(value):
    return '"' + value.replace('"', '""') + '"'


def prepare(document, packets, reader_source):
    """Wire the complete byte guard before all selected projector reads."""
    if set(packets) != set(PROJECTORS):
        raise ValueError('All three accepted issuer projectors required')
    result = copy.deepcopy(document)
    parts = [part for part in result['definition']['parts'] if part['path'] == PATH]
    if len(parts) != 1:
        raise ValueError('Unique accepted source evidence table required')
    part = parts[0]
    text = base64.b64decode(part['payload'], validate=True).decode()
    if 'PinnedCrosswalkReader=' in text:
        raise ValueError('Reconcile existing byte contract before replacing it')
    contract = {}
    for projector in PROJECTORS:
        packet = packets[projector]
        url, batch, pin = packet['archive_url'], packet['expected_batch'], packet['expected_rule_sha256']
        call = projector + '(ReadStudy,' + ','.join(json.dumps(s) for s in [url, batch, pin])
        if text.count(call) != 1:
            raise ValueError('Current native projector pins differ from independently supplied target')
        selected = packet_contract(packet['folder'], url, expected_batch=batch, expected_rule_sha256=pin)
        if set(contract).intersection(selected):
            raise ValueError('Overlapping source packet URLs')
        contract.update(selected)
        text = text.replace(call, call.replace('(ReadStudy,', '(PinnedCrosswalkReader,'))
    payloads = {entry['sha256']: entry['payload'] for entry in contract.values()}
    blobs = '[' + ','.join('#' + mtext(sha) + '=' + mtext(payload) for sha, payload in sorted(payloads.items())) + ']'
    files = '[' + ','.join('#' + mtext(url) + '=[Bytes=' + str(entry['bytes'])
        + ',Payload=PinnedCrosswalkPayloads[#' + mtext(entry['sha256']) + ']]'
        for url, entry in sorted(contract.items())) + ']'
    marker = re.search(r'(?m)^(\t+ *)GNTProjector=', text)
    if not marker:
        raise ValueError('Accepted GNT projector layout missing')
    indent = marker.group(1)
    addition = ('PinnedCrosswalkPayloads=' + blobs + ',\n'
        + 'PinnedCrosswalkFiles=' + files + ',\n'
        + 'PinnedCrosswalkReader=(' + reader_source.rstrip() + ')(ReadStudy,PinnedCrosswalkFiles),\n')
    text = text[:marker.start()] + indent + addition.replace('\n', '\n' + indent) + text[marker.start() + len(indent):]
    part['payload'] = base64.b64encode(text.encode()).decode()
    return result, contract
