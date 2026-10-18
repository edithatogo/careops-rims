"""Local publication identity/review store and immutable candidate releases.

No tenant access, automatic inclusion decision, source download or scheduled delivery.
Uses the downloaded development schema's concepts with versioned source evidence.
"""
from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid

from collect_pubmed import atomic_json, canonical_json
from export_publication_register import EXPORT_FIELDS, export_errors, key_hash, safe_link


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return parsed.astimezone(dt.timezone.utc).isoformat()


def identifiers(row):
    result = {}
    if row.get('pmid'):
        pmid = str(row['pmid']).strip()
        if not re.fullmatch(r'[1-9][0-9]*', pmid):
            raise ValueError('Invalid PMID')
        result['pmid'] = pmid
    if row.get('doi'):
        doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', row['doi'].strip(), flags=re.I).lower()
        if not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
            raise ValueError('Invalid DOI')
        result['doi'] = doi
    if row.get('openalex_id'):
        oaid = str(row['openalex_id']).strip().split('/')[-1]
        if re.fullmatch(r'W\d+', oaid):
            result['openalex'] = oaid
    if row.get('dimensions_id'):
        dimid = str(row['dimensions_id']).strip()
        result['dimensions'] = dimid
    if row.get('scopus_id'):
        scopus_id = str(row['scopus_id']).strip()
        result['scopus'] = scopus_id
    return result


def date_fields(parts):
    raw = '; '.join(f'{key}={value}' for key, value in parts.items())
    try:
        year = int(parts['Year'])
        if not 1 <= year <= 9999:
            raise ValueError()
        if not parts.get('Month'):
            return raw, 'year', year, None
        months = {name.lower(): index for index, name in enumerate(calendar.month_abbr) if name}
        month_value = str(parts['Month'])
        month = int(month_value) if month_value.isdecimal() else months[month_value.lower()]
        day = int(parts.get('Day', 1))
        dt.date(year, month, day)
        return raw, 'day' if parts.get('Day') else 'month', year, f'{year:04d}-{month:02d}'
    except (KeyError, ValueError, TypeError):
        return raw, 'unknown', None, None


class Registry:
    def __init__(self, path, data_kind):
        if data_kind not in {'synthetic', 'live_export'}:
            raise ValueError('Explicit data_kind required')
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publication (
              id TEXT PRIMARY KEY, first_seen TEXT NOT NULL, first_kind TEXT NOT NULL,
              review_status TEXT NOT NULL DEFAULT 'needs_review');
            CREATE TABLE IF NOT EXISTS identifier (
              kind TEXT NOT NULL, value TEXT NOT NULL, publication_id TEXT NOT NULL REFERENCES publication(id),
              PRIMARY KEY(kind,value), UNIQUE(kind,publication_id));
            CREATE TABLE IF NOT EXISTS run (
              id TEXT PRIMARY KEY, source TEXT NOT NULL, content_hash TEXT NOT NULL,
              observed_at TEXT NOT NULL, ingestion_kind TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS run_result (run_id TEXT PRIMARY KEY REFERENCES run(id), publication_ids TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publication_alias (old_id TEXT PRIMARY KEY, canonical_id TEXT NOT NULL REFERENCES publication(id), reason TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS run_item (run_id TEXT NOT NULL REFERENCES run(id), source_id TEXT NOT NULL, content_hash TEXT NOT NULL, PRIMARY KEY(run_id,source_id));
            CREATE TABLE IF NOT EXISTS source_record (
              source TEXT NOT NULL, source_id TEXT NOT NULL,
              publication_id TEXT NOT NULL REFERENCES publication(id), latest_hash TEXT NOT NULL,
              PRIMARY KEY(source,source_id));
            CREATE TABLE IF NOT EXISTS source_version (
              source TEXT NOT NULL, source_id TEXT NOT NULL, content_hash TEXT NOT NULL,
              run_id TEXT NOT NULL REFERENCES run(id), payload TEXT NOT NULL,
              PRIMARY KEY(source,source_id,content_hash));
            CREATE TABLE IF NOT EXISTS conflict (
              run_id TEXT NOT NULL REFERENCES run(id), source_id TEXT NOT NULL,
              reason TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(run_id,source_id));
            CREATE TABLE IF NOT EXISTS review_event (
              id TEXT PRIMARY KEY, publication_id TEXT NOT NULL REFERENCES publication(id),
              status TEXT NOT NULL, reason TEXT NOT NULL, actor TEXT NOT NULL, decided_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attribution_resolution (
              publication_id TEXT PRIMARY KEY REFERENCES publication(id), authors TEXT NOT NULL,
              facilities TEXT NOT NULL, evidence TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS identity_decision (
              id TEXT PRIMARY KEY, donor TEXT NOT NULL, target TEXT NOT NULL,
              evidence TEXT NOT NULL, corrections TEXT NOT NULL, reason TEXT NOT NULL,
              actor TEXT NOT NULL, decided_at TEXT NOT NULL);
        ''')
        existing = self.db.execute("SELECT value FROM metadata WHERE key='data_kind'").fetchone()
        if existing and existing[0] != data_kind:
            self.db.close()
            raise ValueError('Cannot mix synthetic and live registry data')
        self.data_kind = data_kind
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('data_kind',?)", (data_kind,))

    def close(self):
        self.db.close()

    def ingest(self, rows, run_id, source, observed_at, ingestion_kind):
        observed_at = timestamp(observed_at)
        supported_sources = {'pubmed', 'dora', 'openalex', 'crossref', 'dimensions', 'scopus', 'wos', 'ardc'}
        if source not in supported_sources or ingestion_kind not in {'baseline', 'incremental'}:
            raise ValueError('Unsupported source or ingestion kind')
        if not isinstance(rows, list) or not run_id:
            raise ValueError('Rows and run identity required')
        seen = set()
        for row in rows:
            key = row.get('source_record_id')
            if row.get('source') != source or not isinstance(key, str) or not key or key in seen:
                raise ValueError('Invalid or duplicate source identity')
            if not row.get('title') or not safe_link(row.get('url')):
                raise ValueError('Title and approved HTTPS source URL required')
            if not isinstance(row.get('publication_date_parts', {}), dict) or not isinstance(row.get('authors', []), list):
                raise ValueError('Invalid date or author structure')
            identifiers(row)
            seen.add(key)
        content_hash = digest({'source': source, 'rows': rows, 'observed_at': observed_at, 'kind': ingestion_kind})
        previous = self.db.execute('SELECT content_hash FROM run WHERE id=?', (run_id,)).fetchone()
        if previous and previous[0] != content_hash:
            raise ValueError('Run ID already exists with different content')
        if previous:
            return json.loads(self.db.execute('SELECT publication_ids FROM run_result WHERE run_id=?', (run_id,)).fetchone()[0])
        result = []
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO run VALUES (?,?,?,?,?)', (run_id, source, content_hash, observed_at, ingestion_kind))
            for row in rows:
                sid, ids, row_hash = row['source_record_id'], identifiers(row), digest(row)
                self.db.execute('INSERT INTO run_item VALUES (?,?,?)', (run_id, sid, row_hash))
                self.db.execute('INSERT OR IGNORE INTO source_version VALUES (?,?,?,?,?)',
                                (source, sid, row_hash, run_id, canonical_json(row)))
                mapping = self.db.execute('SELECT publication_id FROM source_record WHERE source=? AND source_id=?', (source, sid)).fetchone()
                if mapping:
                    # Reapply only an explicitly reviewed exact old/new correction
                    # to the already mapped source. Raw source_version is retained.
                    for decision in self.db.execute('SELECT corrections FROM identity_decision WHERE target=? ORDER BY decided_at', (mapping[0],)):
                        for kind, correction in json.loads(decision[0]).items():
                            if ids.get(kind) == correction['old']:
                                ids[kind] = correction['new']
                matches = {r[0] for kind, value in ids.items() for r in self.db.execute('SELECT publication_id FROM identifier WHERE kind=? AND value=?', (kind, value))}
                if mapping:
                    matches.add(mapping[0])
                # A source-only record may acquire identifiers belonging to an
                # established record. Preserve its old key as an explicit alias;
                # never combine contradictory identifiers or reviewed decisions.
                if mapping and len(matches) == 2:
                    donor = mapping[0]
                    target = next(p for p in matches if p != donor)
                    donor_ids = list(self.db.execute('SELECT kind,value FROM identifier WHERE publication_id=?', (donor,)))
                    decisions = self.db.execute('SELECT count(*) FROM review_event WHERE publication_id IN (?,?)', (donor, target)).fetchone()[0]
                    decisions += self.db.execute('SELECT count(*) FROM attribution_resolution WHERE publication_id IN (?,?)', (donor, target)).fetchone()[0]
                    target_ids = dict(self.db.execute('SELECT kind,value FROM identifier WHERE publication_id=?', (target,)))
                    if not donor_ids and not decisions and all(k not in target_ids or target_ids[k] == v for k, v in ids.items()):
                        first = self.db.execute('SELECT first_seen,first_kind FROM publication WHERE id IN (?,?) ORDER BY first_seen LIMIT 1', (donor, target)).fetchone()
                        self.db.execute('UPDATE publication SET first_seen=?,first_kind=? WHERE id=?', (*first, target))
                        self.db.execute('UPDATE source_record SET publication_id=? WHERE publication_id=?', (target, donor))
                        self.db.execute('UPDATE publication_alias SET canonical_id=? WHERE canonical_id=?', (target, donor))
                        self.db.execute('INSERT INTO publication_alias VALUES (?,?,?)', (donor, target, 'Source-only identity enriched with exact identifier match'))
                        self.db.execute('DELETE FROM publication WHERE id=?', (donor,))
                        matches = {target}
                conflict = len(matches) > 1
                pid = next(iter(matches)) if len(matches) == 1 else None
                if pid:
                    existing = dict(self.db.execute('SELECT kind,value FROM identifier WHERE publication_id=?', (pid,)))
                    conflict |= any(kind in existing and existing[kind] != value for kind, value in ids.items())
                if conflict:
                    self.db.execute('INSERT OR IGNORE INTO conflict(run_id,source_id,reason) VALUES (?,?,?)',
                                    (run_id, sid, 'Contradictory identifiers; manual reconciliation required'))
                    continue
                if pid is None:
                    pid = 'PUB:' + uuid.uuid4().hex
                    self.db.execute('INSERT INTO publication(id,first_seen,first_kind) VALUES (?,?,?)', (pid, observed_at, ingestion_kind))
                for kind, value in ids.items():
                    self.db.execute('INSERT OR IGNORE INTO identifier VALUES (?,?,?)', (kind, value, pid))
                self.db.execute('INSERT INTO source_record VALUES (?,?,?,?) ON CONFLICT(source,source_id) DO UPDATE SET latest_hash=excluded.latest_hash', (source, sid, pid, row_hash))
                result.append(pid)
            self.db.execute('INSERT INTO run_result VALUES (?,?)', (run_id, canonical_json(result)))
        return result

    def review(self, pid, status, reason, actor, decided_at):
        if status not in {'included', 'excluded', 'needs_review'} or not reason.strip() or not actor.strip():
            raise ValueError('Explicit review status, reason and actor required')
        with self.db:
            self.db.execute('INSERT INTO review_event VALUES (?,?,?,?,?,?)', (uuid.uuid4().hex, pid, status, reason, actor, timestamp(decided_at)))
            self.db.execute('UPDATE publication SET review_status=? WHERE id=?', (status, pid))

    def unresolved_conflicts(self):
        return self.db.execute('SELECT count(*) FROM conflict WHERE resolved=0').fetchone()[0]

    def record_attribution(self, pid, authors, facilities, evidence):
        if not all(isinstance(values, list) and all(isinstance(v, str) for v in values) for values in (authors, facilities, evidence)):
            raise ValueError('Structured attribution evidence required')
        if not evidence:
            raise ValueError('Attribution evidence required')
        with self.db:
            self.db.execute('INSERT INTO attribution_resolution VALUES (?,?,?,?) ON CONFLICT(publication_id) DO UPDATE SET authors=excluded.authors,facilities=excluded.facilities,evidence=excluded.evidence',
                            (pid, canonical_json(authors), canonical_json(facilities), canonical_json(evidence)))

    def resolve_identity(self, donor, target, evidence, reason, actor, decided_at, corrections=None):
        """Apply a reviewed identity decision, retaining old keys and raw evidence.

        This method never discovers matches. Caller must supply the reviewed
        evidence; conflicting identifiers require an exact old/new correction.
        """
        corrections = corrections or {}
        if donor == target or not reason.strip() or not actor.strip() or not evidence:
            raise ValueError('Distinct identities and explicit decision evidence required')
        if any(not isinstance(e, dict) or not e.get('source') or not re.fullmatch(r'[0-9a-f]{64}', e.get('sha256', '')) for e in evidence):
            raise ValueError('Evidence source and SHA256 required')
        decided_at = timestamp(decided_at)
        with self.db:
            if self.db.execute('SELECT 1 FROM publication_alias WHERE old_id IN (?,?)', (donor,target)).fetchone():
                raise ValueError('Use current identities, not aliases')
            pubs = list(self.db.execute('SELECT * FROM publication WHERE id IN (?,?)', (donor,target)))
            if len(pubs) != 2 or any(p['review_status'] == 'excluded' for p in pubs):
                raise ValueError('Missing identity or exclusion requires separate disposition')
            donor_ids = dict(self.db.execute('SELECT kind,value FROM identifier WHERE publication_id=?', (donor,)))
            target_ids = dict(self.db.execute('SELECT kind,value FROM identifier WHERE publication_id=?', (target,)))
            conflicts = {k for k,v in donor_ids.items() if k in target_ids and target_ids[k] != v}
            if set(corrections) != conflicts:
                raise ValueError('Every identifier conflict needs an exact correction')
            for kind in conflicts:
                if corrections[kind] != {'old':donor_ids[kind], 'new':target_ids[kind]}:
                    raise ValueError('Correction does not match current identifiers')
            self.db.execute('INSERT INTO identity_decision VALUES (?,?,?,?,?,?,?,?)',
                            (uuid.uuid4().hex,donor,target,canonical_json(evidence),canonical_json(corrections),reason,actor,decided_at))
            for kind,value in donor_ids.items():
                self.db.execute('DELETE FROM identifier WHERE kind=? AND value=?', (kind,value))
                if kind not in target_ids:
                    self.db.execute('INSERT INTO identifier VALUES (?,?,?)', (kind,value,target))
            self.db.execute('UPDATE source_record SET publication_id=? WHERE publication_id=?', (target,donor))
            self.db.execute('UPDATE publication_alias SET canonical_id=? WHERE canonical_id=?', (target,donor))
            self.db.execute('INSERT INTO publication_alias VALUES (?,?,?)', (donor,target,reason))
            first = min(pubs, key=lambda p:p['first_seen'])
            self.db.execute('UPDATE publication SET first_seen=?,first_kind=? WHERE id=?', (first['first_seen'],first['first_kind'],target))
            resolutions=list(self.db.execute('SELECT * FROM attribution_resolution WHERE publication_id IN (?,?)',(donor,target)))
            if resolutions:
                values=[sorted({v for r in resolutions for v in json.loads(r[field])}) for field in ('authors','facilities','evidence')]
                self.db.execute('INSERT INTO attribution_resolution VALUES (?,?,?,?) ON CONFLICT(publication_id) DO UPDATE SET authors=excluded.authors,facilities=excluded.facilities,evidence=excluded.evidence',
                                (target,*(canonical_json(v) for v in values)))

    def records(self):
        output = []
        for pub in self.db.execute('SELECT * FROM publication WHERE id NOT IN (SELECT old_id FROM publication_alias) ORDER BY id'):
            versions = self.db.execute('''SELECT s.source,v.payload FROM source_record s
                JOIN source_version v ON v.source=s.source AND v.source_id=s.source_id AND v.content_hash=s.latest_hash
                WHERE s.publication_id=? ORDER BY CASE s.source WHEN 'pubmed' THEN 0 ELSE 1 END,s.source_id''', (pub['id'],)).fetchall()
            payload = json.loads(versions[0]['payload'])
            ids = dict(self.db.execute('SELECT kind,value FROM identifier WHERE publication_id=?', (pub['id'],)))
            sources = {v['source'] for v in versions}
            raw, precision, year, month = date_fields(payload.get('publication_date_parts', {}))
            raw = payload.get('publication_date_raw') or raw
            if versions[0]['source'] == 'dora' and payload.get('date_basis') != 'publication_verified':
                raw, precision, year, month = str(payload.get('raw_feed_date', raw)), 'rss_unverified', None, None
            source_labels = {
                'pubmed': 'PubMed', 'dora': 'DORA', 'openalex': 'OpenAlex', 'crossref': 'Crossref',
                'dimensions': 'Dimensions', 'scopus': 'Scopus', 'wos': 'Web of Science', 'ardc': 'ARDC'
            }
            ordered_sources = [source_labels[s] for s in source_labels if s in sources]
            row = dict.fromkeys(EXPORT_FIELDS)
            row.update(CanonicalKey=pub['id'], Title=payload['title'], Journal=payload.get('journal'),
                       Authors='; '.join(a.get('name', '') for a in payload.get('authors', [])),
                       PublicationDateRaw=raw, PublicationDatePrecision=precision, PublicationYear=year,
                       PublicationMonth=month, PMID=ids.get('pmid'), DOI=ids.get('doi'),
                       SourceSet='; '.join(ordered_sources),
                       AttributionStatus=pub['review_status'], DedupMethod='persistent-source/identifier',
                       AttributionEvidence='; '.join(sorted({a for v in versions for author in json.loads(v['payload']).get('authors', []) for a in author.get('affiliations', [])})))
            for v in versions:
                row['PubMedURL' if v['source'] == 'pubmed' else 'DORAURL'] = json.loads(v['payload'])['url']
            extra_evidence = [json.loads(v['payload']).get('attribution_evidence', '') for v in versions]
            row['AttributionEvidence'] = '; '.join(filter(None, [row['AttributionEvidence'], *extra_evidence]))
            resolved = self.db.execute('SELECT * FROM attribution_resolution WHERE publication_id=?', (pub['id'],)).fetchone()
            if resolved:
                row['CHHHSAffiliatedAuthors'] = '; '.join(json.loads(resolved['authors']))
                row['MatchedFacilities'] = '; '.join(json.loads(resolved['facilities']))

            # Extract extended enrichment across versions
            openalex_cites = None
            crossref_cites = None
            scopus_cites = None
            oa_status = None
            oa_url = None
            funders = []
            grants = []
            mesh = []
            keywords = []
            affil_raw = []
            affil_hier = []
            metrics_utc = None

            for v in versions:
                p = json.loads(v['payload'])
                if p.get('CitationCount_OpenAlex') is not None:
                    openalex_cites = p['CitationCount_OpenAlex']
                if p.get('CitationCount_Crossref') is not None:
                    crossref_cites = p['CitationCount_Crossref']
                if p.get('CitationCount_Scopus') is not None:
                    scopus_cites = p['CitationCount_Scopus']
                if p.get('OpenAccessStatus'):
                    oa_status = p['OpenAccessStatus']
                if p.get('OAUrl'):
                    oa_url = p['OAUrl']
                if p.get('FunderNames'):
                    for f in str(p['FunderNames']).split(';'):
                        clean_f = f.strip()
                        if clean_f and clean_f not in funders:
                            funders.append(clean_f)
                if p.get('GrantIDs'):
                    for g in str(p['GrantIDs']).split(';'):
                        clean_g = g.strip()
                        if clean_g and clean_g not in grants:
                            grants.append(clean_g)
                if p.get('MeSHHeadings'):
                    for m in str(p['MeSHHeadings']).split(';'):
                        clean_m = m.strip()
                        if clean_m and clean_m not in mesh:
                            mesh.append(clean_m)
                if p.get('AuthorKeywords'):
                    for k in str(p['AuthorKeywords']).split(';'):
                        clean_k = k.strip()
                        if clean_k and clean_k not in keywords:
                            keywords.append(clean_k)
                if p.get('AffiliationsRaw'):
                    for a in str(p['AffiliationsRaw']).split(';'):
                        clean_a = a.strip()
                        if clean_a and clean_a not in affil_raw:
                            affil_raw.append(clean_a)
                if p.get('AffiliationHierarchy'):
                    for h in str(p['AffiliationHierarchy']).split(';'):
                        clean_h = h.strip()
                        if clean_h and clean_h not in affil_hier:
                            affil_hier.append(clean_h)
                if p.get('CitationMetricsObservedUTC'):
                    metrics_utc = p['CitationMetricsObservedUTC']

            row.update(
                CitationCount_OpenAlex=openalex_cites,
                CitationCount_Crossref=crossref_cites,
                CitationCount_Scopus=scopus_cites,
                OpenAccessStatus=oa_status,
                OAUrl=oa_url,
                FunderNames='; '.join(funders) if funders else None,
                GrantIDs='; '.join(grants) if grants else None,
                MeSHHeadings='; '.join(mesh) if mesh else None,
                AuthorKeywords='; '.join(keywords) if keywords else None,
                AffiliationsRaw='; '.join(affil_raw) if affil_raw else None,
                AffiliationHierarchy='; '.join(affil_hier) if affil_hier else None,
                CitationMetricsObservedUTC=metrics_utc,
                FirstObservedAt=pub['first_seen'],
                FirstIngestionKind=pub['first_kind'],
                ReviewStatus=pub['review_status'],
            )
            output.append(row)
        return output

    def stage(self, root, release_id, source_status):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', release_id):
            raise ValueError('Unsafe release ID')
        folder = Path(root) / release_id
        folder.mkdir(parents=True, exist_ok=False)
        records = self.records()
        coverage = 'Provisional source-attributed registry; not an institutional census. ' + canonical_json(source_status).strip()
        full = [{k: r[k] for k in EXPORT_FIELDS} for r in records if r['ReviewStatus'] != 'excluded']
        def envelope(rows, month=None):
            value = {'data_kind': self.data_kind, 'scope': {'mode': 'month' if month else 'all', 'reporting_month': month},
                     'source_snapshot_id': release_id, 'coverage_note': coverage,
                     'expected_canonical_count': len(rows), 'expected_key_sha256': key_hash(rows), 'records': rows}
            errors = export_errors(value)
            if errors:
                raise ValueError('; '.join(errors))
            return value
        atomic_json(folder / 'all-publications.json', envelope(full))
        atomic_json(folder / 'registry-metadata.json', records)
        atomic_json(folder / 'identity-aliases.json', [dict(r) for r in self.db.execute('SELECT * FROM publication_alias ORDER BY old_id')])
        atomic_json(folder / 'identity-decisions.json', [dict(r) for r in self.db.execute('SELECT * FROM identity_decision ORDER BY decided_at,id')])
        atomic_json(folder / 'review-events.json', [dict(r) for r in self.db.execute('SELECT * FROM review_event ORDER BY decided_at,id')])
        (folder / 'monthly').mkdir()
        for month in sorted({r['PublicationMonth'] for r in full if r['PublicationMonth']}):
            atomic_json(folder / 'monthly' / (month + '.json'), envelope([r for r in full if r['PublicationMonth'] == month], month))
        manifest = {'release_id': release_id, 'data_kind': self.data_kind, 'source_status': source_status,
                    'unresolved_conflicts': self.unresolved_conflicts(), 'needs_review': sum(r['ReviewStatus'] == 'needs_review' for r in records),
                    'included_keys': [r['CanonicalKey'] for r in records if r['ReviewStatus'] == 'included'],
                    'native_model_reconciled': False,
                    'files': {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*.json')}}
        atomic_json(folder / 'manifest.json', manifest)
        return folder

    def promote(self, folder):
        # Deliberately no promotion path before native readback has been designed
        # and verified. Staging must never overwrite the last good release pointer.
        raise ValueError('Promotion requires native model reconciliation and explicit release acceptance')
