"""Prepare existing paper-library Title/Description from accepted archive evidence.

Offline operator tooling only. No paper analysis, field creation, native mutation,
content rewrite, manifest rewrite or access grant. Apply with an exact item ETag.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urljoin, quote, urlunsplit

START = '<p>RIMS archive metadata v1</p>'
END = '<p>End RIMS archive metadata</p>'


def canonical_html(value, site_origin=None):
    """Qualified SP entities, tag whitespace and same-origin href expansion only."""
    result = html.unescape(value or '')
    if site_origin:
        def link(match):
            parsed = urlsplit(urljoin(site_origin + '/', match[1]))
            if parsed.scheme + '://' + parsed.netloc != site_origin:
                return match[0]
            normalized = urlunsplit((parsed.scheme, parsed.netloc,
                                    quote(parsed.path, safe="/%:@!$&'()*+,;=-._~"),
                                    parsed.query, parsed.fragment))
            return 'href="' + normalized + '"'
        result = re.sub(r'href="([^"]*)"', link, result)
    return re.sub(r'<[^>]+>', lambda m: re.sub(r'\s+', ' ', m.group()), result)


def required_text(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f'{label}: expected nonblank unpadded text')
    return value


def safe_link(value, record=False, doi=None, md5=None):
    required_text(value, 'link')
    url = urlsplit(value)
    pairs = parse_qsl(url.query, keep_blank_values=True)
    query = dict(pairs)
    allowed_query = not url.query or (record and re.fullmatch(r'ID=[1-9][0-9]*', url.query))
    if len(query) == len(pairs) and not record:
        allowed_query = allowed_query or (
            url.hostname == 'pmc-oa-opendata.s3.amazonaws.com'
            and set(query) == {'md5'} and query['md5'] == md5
            and isinstance(md5, str) and re.fullmatch('[a-f0-9]{32}', md5)) or (
            url.hostname == 'journals.plos.org' and set(query) == {'id', 'type'}
            and query['id'] == doi and query['type'] == 'printable')
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.fragment or not allowed_query):
        raise ValueError('Metadata links require HTTPS and only qualified non-sensitive provider/record queries')
    return '<a href="' + html.escape(value, quote=True) + '">' + html.escape(value) + '</a>'


def prepare(snapshot):
    row, manifest, file, item = (snapshot[k] for k in ['parent', 'manifest', 'file', 'item'])
    if row['OAArchiveState'] != 'linked' or manifest.get('state') != 'linked':
        raise ValueError('Only linked current papers; preserve saved-but-unlinked recovery')
    if (manifest['CanonicalKey'] != row['field_2'] or manifest['DOI'] != row['field_11']
            or file['UniqueId'] != manifest['verified_file_unique_id']
            or file['ServerRelativeUrl'] != manifest['folder'] + '/paper.pdf'
            or file['Name'] != 'paper.pdf' or file['CheckOutType'] != 2
            or manifest['sha256_status'] != 'verified_native_readback'
            or snapshot['sha256'] != manifest['sha256']
            or snapshot['bytes'] != int(file['Length'])
            or not re.fullmatch('[a-f0-9]{64}', manifest['sha256'])):
        raise ValueError('Exact current archive identity/integrity/checkout evidence required')
    etag = item.get('odata.etag') or item.get('@odata.etag')
    if not etag or etag == '*':
        raise ValueError('Exact native item ETag required')
    if row['OAArchiveURL']['Url'] != manifest['file_url']:
        raise ValueError('Preserve edited or mismatched archive link')
    title = required_text(row['Title'], 'canonical title')
    version = required_text(manifest['article_version'], 'article version')
    if version not in {'publishedVersion', 'acceptedVersion', 'submittedVersion'}:
        raise ValueError('Unknown article version; preserve source uncertainty')
    # UTF16 length matches the native Text field, without splitting a surrogate.
    suffix = ' | ' + version
    budget = 510 - len(suffix.encode('utf-16-le'))
    proposed_title = title.encode('utf-16-le')[:budget].decode('utf-16-le', errors='ignore').rstrip() + suffix
    values = [
        ('Canonical publication', required_text(manifest['CanonicalKey'], 'CanonicalKey')),
        ('DOI', required_text(manifest['DOI'], 'DOI')),
        ('Source', required_text(manifest['source'], 'source')),
        ('Article version', version),
        ('Licence', required_text(manifest['licence'], 'licence')),
        ('Retrieved UTC', required_text(manifest['retrieved_utc'], 'retrieved UTC')),
        ('Content SHA256', manifest['sha256']),
    ]
    block = START + ''.join('<p>' + label + ': ' + html.escape(value) + '</p>' for label, value in values)
    block += '<p>Source URL: ' + safe_link(manifest['source_url'], doi=manifest['DOI'], md5=manifest.get('md5')) + '</p>'
    # Register link retains the authoritative complete manifest and version history.
    block += '<p>Authoritative archive provenance: ' + safe_link(snapshot['register_url'], record=True) + '</p>'
    block += '<p>Library properties describe this current copy; the register manifest and saved receipt remain authoritative. No scientific review or authority to issue is implied.</p>' + END
    old = item.get('OData__ExtendedDescription') or ''
    location = urlsplit(manifest['file_url'])
    origin = location.scheme + '://' + location.netloc
    normalized = canonical_html(old, origin)
    if START in normalized or END in normalized:
        if normalized.count(START) != 1 or normalized.count(END) != 1:
            raise ValueError('Preserve malformed/duplicated managed metadata; reconcile first')
        existing = normalized[normalized.index(START):normalized.index(END) + len(END)]
        if existing != canonical_html(block, origin):
            raise ValueError('Preserve changed managed metadata; reconcile source or human edits')
        description = old
    else:
        description = old + block
    if len(description) > 60000:
        raise ValueError('Preserve oversized Description')
    changes = {}
    if item.get('Title') in (None, ''):
        changes['Title'] = proposed_title
    if canonical_html(description, origin) != normalized:
        changes['OData__ExtendedDescription'] = description
    return {'file_id': file['UniqueId'], 'item_id': item['Id'], 'item_url': snapshot['item_url'],
            'parent_id': row['Id'], 'etag': etag, 'sha256': snapshot['sha256'],
            'file_url': manifest['file_url'], 'file_preimage': file,
            'parent_preimage_sha256': hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
            'before': {k: item.get(k) for k in changes}, 'changes': changes,
            'preserved_human_title': bool(item.get('Title')), 'content_writes': False,
            'manifest_writes': False, 'action': 'update' if changes else 'unchanged'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    raw = args.snapshot.read_bytes()
    plan = prepare(json.loads(raw))
    plan['snapshot_path'] = str(args.snapshot.resolve())
    plan['snapshot_sha256'] = hashlib.sha256(raw).hexdigest()
    with args.output.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    print('PREPARED_LOCAL_ONLY: ' + plan['action'] + '; content/manifest unchanged')


if __name__ == '__main__':
    main()
