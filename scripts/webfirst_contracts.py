"""Local web-first policy gates. No Power BI, browser or VM is controlled by this module."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ('read_report', 'read_model', 'edit_report', 'edit_model', 'edit_power_query', 'refresh', 'export_rows')
LIVE_CHECKS = ('native_m', 'native_dax', 'live_refresh', 'report_readback', 'model_readback', 'rendered_pages',
               'full_export_reconciliation', 'monthly_export_reconciliation', 'legacy_metadata_scan', 'fixture_exclusion')
FALLBACK_REASONS = {'unsupported_web_model_type', 'unsupported_web_power_query_operation',
                    'unsupported_required_web_authoring_operation'}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def choose_route(manifest: dict[str, Any]) -> dict[str, Any]:
    """Route on recorded capabilities; a route is not proof of native execution."""
    selected, unverified, missing = {}, [], []
    candidates = manifest.get('capabilities', [])
    if not isinstance(candidates, list):
        candidates = []
    for operation in CAPABILITIES:
        matches = [c for c in candidates if isinstance(c, dict) and c.get('operation') == operation
                   and c.get('provider') in {'plugin', 'webui', 'assisted_webui'}
                   and c.get('status') in {'verified', 'available'}
                   and isinstance(c.get('evidence_ref'), str) and c['evidence_ref'].strip()]
        if not matches:
            missing.append(operation)
            continue
        matches.sort(key=lambda c: (c['status'] != 'verified', c['provider'] != 'plugin'))
        chosen = matches[0]; selected[operation] = chosen['provider']
        if chosen['status'] != 'verified':
            unverified.append(operation)
    route = ('blocked_permissions' if manifest.get('permission_denied') is True
             else 'needs_capability_verification' if missing else 'web_first')
    return {'route': route, 'operation_routes': selected, 'missing_operations': missing,
            'unverified_operations': unverified, 'live_acceptance': False, 'fallback_authorised': False}


def isolation_errors(state: dict[str, Any]) -> list[str]:
    errors = []
    names = ['tenant_id', 'workspace_id', 'original_report_id', 'original_model_id',
             'development_report_id', 'development_model_id']
    for name in names:
        try:
            UUID(state.get(name, ''))
        except (ValueError, TypeError, AttributeError):
            errors.append('Valid exact UUID required: ' + name)
    if state.get('original_model_id') == state.get('development_model_id'):
        errors.append('The development report still shares the original semantic model')
    if state.get('original_report_id') == state.get('development_report_id'):
        errors.append('The original report is not an isolated development report')
    for name in ['dependency_inventory_complete', 'recovery_verified', 'baseline_unchanged', 'canary_roundtrip_verified']:
        if state.get(name) is not True:
            errors.append('Evidence required: ' + name)
    return errors


def fallback_errors(decision: dict[str, Any]) -> list[str]:
    errors = []
    if decision.get('reason') not in FALLBACK_REASONS:
        errors.append('Not a verified web-authoring incompatibility eligible for VM fallback')
    for name in ['webui_attempted', 'blocker_confirmed', 'permissions_ok', 'owner_approved']:
        if decision.get(name) is not True:
            errors.append('Fallback gate not satisfied: ' + name)
    refs = decision.get('evidence_refs')
    if not isinstance(refs, list) or not refs or not all(isinstance(s, str) and s.strip() for s in refs):
        errors.append('Recorded blocker evidence references are required')
    return errors


def runtime_hashes(root: Path) -> dict[str, str]:
    """Freeze the exact authored definitions, including unexpected hidden files."""
    output = {}
    for directory in ['powerbi', 'powerquery']:
        for path in sorted((root/directory).rglob('*')):
            if path.is_file():
                output[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return output


def live_evidence_errors(evidence: dict[str, Any], evidence_root: Path) -> list[str]:
    """Check evidence-file structure/integrity; an authorised reviewer authenticates it."""
    errors: list[str] = []
    start = finish = None
    try:
        start = datetime.fromisoformat(evidence.get('started_at_utc', ''))
        finish = datetime.fromisoformat(evidence.get('finished_at_utc', ''))
        if start.tzinfo is None or finish.tzinfo is None or finish < start:
            raise ValueError('Invalid observation window')
    except (ValueError, TypeError):
        errors.append('An ordered, timezone-aware live observation window is required')
        start = finish = None
    expected_contract = hashlib.sha256((ROOT/'contracts/web-first-execution.contract.json').read_bytes()).hexdigest()
    if evidence.get('contract_sha256') != expected_contract:
        errors.append('Evidence refers to a missing or stale execution contract')
    if evidence.get('data_kind') != 'live_powerbi':
        errors.append('Native evidence must be declared live_powerbi, not local or synthetic')
    for name in ['tenant_id', 'workspace_id', 'report_id', 'model_id']:
        try:
            UUID(evidence.get('target', {}).get(name, ''))
        except (ValueError, TypeError, AttributeError):
            errors.append('Exact live target required: ' + name)
    if not isinstance(evidence.get('refresh_run_id'), str) or not evidence['refresh_run_id'].strip():
        errors.append('Exact correlated refresh run ID is required')
    if evidence.get('source_health') != {'PubMed': 'success', 'DORA': 'success'}:
        errors.append('Both sources need successful health evidence')
    artifacts = evidence.get('artifacts', [])
    if not isinstance(artifacts, list):
        artifacts = []
    identifiers: set[str] = set()
    valid_artifacts: set[str] = set()
    base = evidence_root.resolve()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append('Artifact must be an object'); continue
        aid, relative = artifact.get('id'), artifact.get('path')
        if not isinstance(aid, str) or not aid or aid in identifiers:
            errors.append('Missing or repeated evidence artifact identifier'); continue
        identifiers.add(aid)
        if not isinstance(relative, str) or not relative:
            errors.append('Evidence artifact path is missing'); continue
        path = (base/relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(base):
            errors.append('Unsafe evidence artifact path: ' + relative); continue
        if any(token in relative.lower() for token in ['fixtures', 'synthetic']):
            errors.append('Fixture path is not live evidence'); continue
        if not path.is_file():
            errors.append('Missing evidence artifact: ' + relative); continue
        if artifact.get('sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
            errors.append('Evidence artifact hash mismatch: ' + relative); continue
        if artifact.get('target') != evidence.get('target'):
            errors.append('Evidence target mismatch: ' + relative); continue
        if artifact.get('refresh_run_id') != evidence.get('refresh_run_id'):
            errors.append('Evidence refresh run mismatch: ' + relative); continue
        try:
            captured = datetime.fromisoformat(artifact.get('captured_at_utc', ''))
            if captured.tzinfo is None or start is None or finish is None or not start <= captured <= finish:
                raise ValueError('Stale observation')
        except (ValueError, TypeError):
            errors.append('Evidence outside the correlated observation window: ' + relative); continue
        valid_artifacts.add(aid)
    checks = evidence.get('checks', {})
    if not isinstance(checks, dict):
        checks = {}
    for name in LIVE_CHECKS:
        check = checks.get(name, {})
        if (not isinstance(check, dict) or check.get('status') != 'pass'
                or check.get('artifact_id') not in valid_artifacts):
            errors.append('Missing substantiated native check: ' + name)
    return errors


def local_validate(root: Path = ROOT) -> dict[str, Any]:
    errors, checks = [], []

    def check(label: str, passed: bool) -> None:
        checks.append({'check': label, 'passed': passed})
        if not passed:
            errors.append(label)

    try:
        contract = load(root/'contracts/web-first-execution.contract.json')
        check('exact seven-page scope', contract['required_pages'] == [
            'CHHHS Publications', 'Monthly Publications',
            'Source Reconciliation', 'Clinical Analytics', 'Funding Opportunities',
            'Funding Calendar', 'My Funding Watchlist'])
        check('canonical-key headline', contract['headline_identity'] == 'CanonicalKey')
        check('both source contracts', contract['sources'] == ['PubMed', 'DORA'])
        check('local tests are not native acceptance', contract['local_validation_is_native_acceptance'] is False)
        check('capability policy matches contract', list(CAPABILITIES) == contract['required_capabilities'])
        check('live-check policy matches contract', list(LIVE_CHECKS) == contract['live_evidence_required'])
        check('fallback policy matches contract', FALLBACK_REASONS == set(contract['fallback_eligible_reasons']))
        frozen = load(root/'contracts/runtime-baseline.manifest.json')
        check('runtime definitions match frozen reviewed baseline', runtime_hashes(root) == frozen['files'])
        check('baseline is explicitly not a native certificate', frozen['native_verified'] is False and type(frozen['known_defects_open']) is bool)
        states = []
        # Dependencies span publication, extension, grant and stabilisation tracks.
        # Keep the original T08-T17 asset checks below, but validate the whole graph.
        graph = {}
        for collection in (root/'conductor/tracks', root/'conductor/archive'):
            if collection.is_dir():
                for path in sorted(collection.glob('*/metadata.json')):
                    metadata = load(path)
                    graph[metadata.get('id', metadata.get('track_id'))] = metadata.get('depends_on', [])
        # Archived tracks remain part of the canonical T08-T17 asset set.
        for collection_name in ('conductor/tracks', 'conductor/archive'):
            for path in sorted((root/collection_name).glob('T*/metadata.json')):
                metadata = load(path); tid = metadata['id']
                number = int(tid.split('_')[0][1:])
                if number < 8 or number > 17:
                    continue
                states.append(metadata); graph[tid] = metadata['depends_on']
                for filename in ['index.md', 'spec.md', 'plan.md', 'prompt.md', 'review.md']:
                    check(tid + ': ' + filename, (path.parent/filename).is_file())
                check(tid + ': recognised status', metadata['status'] in {'pending','in_progress','blocked','gated','complete'})
                if metadata['status'] == 'complete' and metadata['requires_live_evidence']:
                    check(tid + ': live completion has references', bool(metadata.get('completion_evidence')))
                if number in (16, 17):
                    check(tid + ': fallback is conditional', metadata['scope'] == 'conditional_desktop')
        check('exactly ten new tracks', len(states) == 10)
        for tid, dependencies in graph.items():
            check(tid + ': dependency references exist', all(d in graph for d in dependencies))
        visiting, visited = set(), set()

        def visit(tid: str) -> None:
            if tid in visiting:
                raise ValueError('Track dependency cycle')
            if tid in visited:
                return
            visiting.add(tid)
            for dep in graph[tid]:
                if dep not in graph:
                    raise ValueError('Unknown dependency')
                visit(dep)
            visiting.remove(tid); visited.add(tid)

        for tid in graph:
            visit(tid)
        check('acyclic dependency graph', True)
        for tid in ['T05_native_acceptance','T07_fabric_live_acceptance']:
            check(tid + ': superseded not deployed', load(root/f'conductor/tracks/{tid}/metadata.json')['status'] == 'superseded')
        for rel in ['handoff/POWERBI_PLUGIN_START_HERE.md', 'handoff/UTM_FALLBACK.md',
                    'scripts/Inspect-UTM-Host.sh', 'scripts/Inspect-PowerBI-Guest.ps1',
                    'contracts/publication-export.contract.json', 'config/live-evidence.template.json']:
            check('required handoff asset: ' + rel, (root/rel).is_file())
        from export_publication_register import EXPORT_FIELDS, export_errors
        check('export field policy matches contract', EXPORT_FIELDS == load(root/'contracts/publication-export.contract.json')['fields'])
        check('synthetic fixture satisfies export contract', not export_errors(load(root/'tests/fixtures/webfirst-export-synthetic.json')))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(str(error))
    return {'status': 'PASS_LOCAL_ONLY' if not errors else 'FAIL_LOCAL',
            'checks': checks, 'errors': errors, 'native_acceptance': False,
            'live_dashboard_modified': False, 'vm_modified': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'route', 'isolation', 'fallback', 'evidence'])
    parser.add_argument('--input', type=Path)
    parser.add_argument('--evidence-root', type=Path)
    args = parser.parse_args()
    if args.command == 'validate':
        result = local_validate()
    else:
        if args.input is None:
            parser.error('--input is required')
        data = load(args.input)
        if not isinstance(data, dict):
            parser.error('Input must be a JSON object')
        if args.command == 'route':
            result = choose_route(data)
        elif args.command == 'isolation':
            result = {'errors': isolation_errors(data), 'policy_only': True}
        elif args.command == 'fallback':
            result = {'errors': fallback_errors(data), 'policy_only': True, 'vm_modified': False}
        else:
            if args.evidence_root is None:
                parser.error('--evidence-root is required')
            errors = live_evidence_errors(data, args.evidence_root)
            result = {'errors': errors, 'ready_for_authorised_evidence_review': not errors,
                      'independent_live_authentication_performed': False}
    print(json.dumps(result, indent=2))
    if result.get('errors') or result.get('route') in {'blocked_permissions', 'needs_capability_verification'}:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
