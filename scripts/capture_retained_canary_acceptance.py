"""Read one completed isolated-canary refresh, exact definition and retained DAX evidence.

The same dataset ID is used for the request-specific refresh read and every
ExecuteQueries call. Raw responses and the aggregate receipt stay in ignored
private storage. This does not accept canonical/report consumers or registry
admission, and does not submit a refresh or modify a model.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

try:
    from scripts.reconcile_publication_sources import retained_rows
    from scripts.verify_retained_canary_keys import QUERY as KEY_QUERY, model_rows as key_rows, verify as verify_keys
    from scripts.verify_retained_canary_fields import QUERY as FIELD_QUERY, model_rows as field_rows, verify as verify_fields
    from scripts.verify_retained_canary_metadata_values import query as metadata_query, expected as metadata_expected, verify as verify_metadata
    from scripts.verify_retained_native_fixture_cases import QUERY as FIXTURE_QUERY, model_rows as fixture_rows, verify as verify_fixtures
except ModuleNotFoundError:
    from reconcile_publication_sources import retained_rows
    from verify_retained_canary_keys import QUERY as KEY_QUERY, model_rows as key_rows, verify as verify_keys
    from verify_retained_canary_fields import QUERY as FIELD_QUERY, model_rows as field_rows, verify as verify_fields
    from verify_retained_canary_metadata_values import query as metadata_query, expected as metadata_expected, verify as verify_metadata
    from verify_retained_native_fixture_cases import QUERY as FIXTURE_QUERY, model_rows as fixture_rows, verify as verify_fixtures


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = (ROOT / "private").resolve()
BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC = "https://api.fabric.microsoft.com/v1"


def _dataset_api_root(dataset_id: str, workspace_id: str | None = None) -> str:
    """Resolve the explicit dataset route; group datasets must not use My workspace APIs."""
    root = f"{BASE}/datasets/{dataset_id}" if workspace_id is None else f"{BASE}/groups/{workspace_id}/datasets/{dataset_id}"
    if any(c in dataset_id + (workspace_id or "") for c in "/?&#"):
        raise ValueError("dataset and workspace IDs must be path segments")
    return root


def _trusted_fabric_operation_url(value: str | None) -> bool:
    """Fabric may return its authenticated regional WABI operation endpoint."""
    if not value:
        return False
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment or parsed.path.count("/") != 3
            or not parsed.path.startswith("/v1/operations/")):
        return False
    if host != "api.fabric.microsoft.com" and not (host.startswith("wabi-") and host.endswith(".analysis.windows.net")):
        return False
    try:
        UUID(parsed.path.rsplit("/", 1)[1])
    except ValueError:
        return False
    return True


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("UTC timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        # Power BI's refresh detail emits UTC timestamps without a suffix.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_request(history: object) -> str:
    if not isinstance(history, dict) or not isinstance(history.get("value"), list) or not history["value"]:
        raise ValueError("complete latest refresh history required")
    first = history["value"][0]
    if not isinstance(first, dict) or not isinstance(first.get("requestId"), str):
        raise ValueError("latest refresh request ID required")
    return first["requestId"]


def refresh_disposition(refresh_http: int, refresh: object) -> str:
    """Do not describe a terminal refresh failure as a request still running."""
    status = refresh.get("status") if isinstance(refresh, dict) else None
    if refresh_http == 200 and status == "Completed":
        return "COMPLETE"
    if refresh_http in {200, 202} and status in {"Unknown", "InProgress", "NotStarted"}:
        return "WAIT"
    if refresh_http == 200 and status in {"Failed", "Cancelled", "Disabled"}:
        return "TERMINAL_FAILED"
    return "ERROR"


def history_disposition(history_http: int, history: object, request_id: str) -> tuple[str, str | None]:
    """Cross-check a nonterminal detail response against the latest run entry."""
    if history_http != 200:
        return "ERROR", None
    try:
        if _latest_request(history) != request_id:
            return "ERROR", None
        status = history["value"][0].get("status")
    except (KeyError, TypeError, ValueError):
        return "ERROR", None
    if status in {"Failed", "Cancelled", "Disabled"}:
        return "TERMINAL_FAILED", status
    if status in {"Unknown", "InProgress", "NotStarted", "Completed"}:
        return "WAIT", status
    return "ERROR", status


def definition_parts(payload: object, expected_part_count: int = 9) -> dict[str, bytes]:
    """Decode every TMDL part exactly; even one terminal newline is drift."""
    if not isinstance(payload, dict) or not isinstance(payload.get("definition"), dict):
        raise ValueError("complete Fabric definition required")
    definition = payload["definition"]
    parts = definition.get("parts")
    if definition.get("format") != "TMDL" or not isinstance(parts, list) or len(parts) != expected_part_count:
        label = "nine" if expected_part_count == 9 else str(expected_part_count)
        raise ValueError(f"exact {label}-part TMDL definition required")
    decoded = {}
    for part in parts:
        if not isinstance(part, dict) or not isinstance(part.get("path"), str) or not part["path"] or part.get("payloadType") != "InlineBase64":
            raise ValueError("invalid TMDL part")
        if part["path"] in decoded:
            raise ValueError("duplicate TMDL part")
        try:
            decoded[part["path"]] = base64.b64decode(part["payload"], validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid TMDL part payload") from exc
    return decoded


def definition_digest(payload: object, expected: object, expected_part_count: int = 9) -> str:
    actual_parts = definition_parts(payload, expected_part_count)
    expected_parts = definition_parts(expected, expected_part_count)
    if actual_parts != expected_parts:
        raise ValueError("live definition differs from saved exact readback")
    digest = hashlib.sha256()
    for path, data in sorted(actual_parts.items()):
        digest.update(path.encode() + b"\0" + len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def evaluate(refresh_http: int, refresh: object, history_before: object,
             history_after: object, request_id: str, key_payload: object,
             field_payload: object, archive: list[dict], captured_at: str,
             definition_before: object, definition_after: object,
             expected_definition: object, expected_part_count: int = 9,
             fixture_payload: object | None = None,
             target_scope: str | None = None,
             expected_tables: list[str] | None = None) -> dict:
    """Validate the terminal response before evaluating any DAX response."""
    if target_scope is None:
        if expected_part_count == 36:
            raise ValueError("36-part acceptance requires explicit target_scope: isolated or report_bound")
        target_scope = "isolated"
    if target_scope not in {"isolated", "report_bound"}:
        raise ValueError("target_scope must be isolated or report_bound")
    if refresh_http != 200 or not isinstance(refresh, dict) or refresh.get("status") != "Completed":
        raise ValueError("request-specific refresh must be terminal Completed")
    if expected_tables is not None:
        objects = refresh.get("objects")
        observed_tables = [row.get("table") for row in objects if isinstance(row, dict)] if isinstance(objects, list) else []
        if (not expected_tables or len(expected_tables) != len(set(expected_tables))
                or set(observed_tables) != set(expected_tables)
                or len(observed_tables) != len(expected_tables)
                or any(row.get("status") != "Completed" for row in objects)):
            raise ValueError("terminal refresh objects differ from the exact requested table scope")
    ended = _utc(refresh.get("endTime"))
    started = _utc(refresh.get("startTime"))
    if ended < started or _utc(captured_at) < ended:
        raise ValueError("query capture must follow the completed refresh")
    if _latest_request(history_before) != request_id or _latest_request(history_after) != request_id:
        raise ValueError("a different refresh was latest before or after the DAX reads")
    before_digest = definition_digest(definition_before, expected_definition, expected_part_count)
    after_digest = definition_digest(definition_after, expected_definition, expected_part_count)
    if before_digest != after_digest:
        raise ValueError("canary definition changed across the DAX reads")
    key_receipt, key_differences = verify_keys(key_rows(key_payload), archive)
    field_receipt, field_differences = verify_fields(field_rows(field_payload), archive)
    fixture_receipt = None
    fixture_differences = None
    if fixture_payload is not None:
        fixture_receipt, fixture_differences = verify_fixtures(fixture_rows(fixture_payload))
    if target_scope == "report_bound":
        key_receipt["scope"] = "processed retained keys in the report-bound DEV model; registry admission and report rendering remain separate"
        field_receipt["scope"] = "processed retained fields in the report-bound DEV model; complete metadata, registry admission and report rendering remain separate"
    else:
        key_receipt["scope"] = "processed retained keys in the isolated model; canonical/report consumers, registry admission and report rendering remain separate"
        field_receipt["scope"] = "processed retained fields in the isolated model; complete metadata, canonical/report consumers, registry admission and report rendering remain separate"
    receipt = {
        "kind": "retained_canary_request_correlated_acceptance_v1",
        "status": "PASS" if key_receipt["status"] == field_receipt["status"] == "PASS"
        and (fixture_receipt is None or fixture_receipt["status"] == "PASS") else "FAIL",
        "target_scope": target_scope,
        "refresh_status": refresh["status"],
        "requested_refresh_tables": expected_tables,
        "refresh_start_utc": started.isoformat(),
        "refresh_end_utc": ended.isoformat(),
        "query_capture_utc": _utc(captured_at).isoformat(),
        "exact_definition_sha256": before_digest,
        "key_parity": key_receipt,
        "field_integrity": field_receipt,
        "difference_counts": {
            "key_duplicates": len(key_differences["duplicate"]),
            "key_missing": len(key_differences["missing"]),
            "key_extra": len(key_differences["extra"]),
            "field_issue_rows": len(field_differences["issues"]),
        },
        "scope": ("one report-bound DEV model request and post-completion DAX reads; report rendering, registry admission and later cycles remain separate"
                  if target_scope == "report_bound" else
                  "one isolated model request and post-completion DAX reads; canonical/report consumer, full metadata parity, registry admission and later cycles remain separate"),
    }
    if fixture_receipt is not None:
        receipt["native_fixture_validation"] = fixture_receipt
        receipt["native_fixture_differences"] = fixture_differences
        for name in ("missing", "extra", "duplicate", "failed"):
            receipt["difference_counts"][f"fixture_{name}"] = len(fixture_differences[name])
        receipt["scope"] += "; exact native fixture outcomes correlated to this completed request"
    return receipt


def _token_for(resource: str) -> str:
    data = json.loads(subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", resource, "--output", "json"],
        timeout=20,
    ))
    token = data.get("accessToken")
    if not isinstance(token, str) or not token:
        raise ValueError("Azure CLI did not provide a Power BI access token")
    return token


def _call(url: str, token: str, query: str | None = None) -> tuple[int, dict]:
    body = None if query is None else json.dumps({"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}}).encode()
    request = Request(url, data=body, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=45) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


class FabricDefinitionPending(TimeoutError):
    """Observation ended; operation metadata is retained for same-handle resume."""
    def __init__(self, metadata):
        super().__init__('Fabric definition remains unproven; resume the retained operation, do not repost')
        self.operation_metadata = metadata


def _fabric_definition(workspace_id: str, dataset_id: str, token: str,
                       *, resume_operation: dict | None = None,
                       operation_receipt: Path | None = None) -> dict:
    """Read one bounded Fabric definition operation without model mutation."""
    # Resolve and validate a caller-supplied receipt before the initiating POST.
    receipt_path = _private(operation_receipt) if operation_receipt is not None else None
    url = f"{FABRIC}/workspaces/{workspace_id}/semanticModels/{dataset_id}/getDefinition"
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if resume_operation is not None:
        if (resume_operation.get('workspace_id') != workspace_id
                or resume_operation.get('dataset_id') != dataset_id):
            raise ValueError('Definition operation belongs to another target')
        metadata = dict(resume_operation)
        operation_url = metadata.get('operation_url')
    else:
        with urlopen(Request(url, data=b"", headers=headers, method="POST"), timeout=30) as response:
            if response.status == 200:
                return json.loads(response.read())
            if response.status != 202:
                raise ValueError("Fabric Get Definition did not return 200 or 202")
            operation_url = response.headers.get("Location")
            metadata = {'workspace_id':workspace_id,'dataset_id':dataset_id,
                        'operation_url':operation_url,'operation_id':response.headers.get('x-ms-operation-id'),
                        'retry_after':response.headers.get('Retry-After'),'status':'Pending'}
    if not _trusted_fabric_operation_url(operation_url):
        raise ValueError("Fabric Get Definition did not return a trusted operation URL")
    def save():
        if receipt_path is not None:
            # Persist only operation identity/state; never copy arbitrary caller
            # fields (which could include credentials) into the private receipt.
            safe = {key: metadata.get(key) for key in (
                'workspace_id', 'dataset_id', 'operation_url', 'operation_id',
                'retry_after', 'status', 'error') if key in metadata}
            serialized = json.dumps(safe,indent=2)
            if token:
                serialized = serialized.replace(token, '[REDACTED]')
            receipt_path.write_text(serialized+'\n')

    def observe_failure(exc):
        save()
        if isinstance(exc, HTTPError):
            # Preserve the concrete HTTP status/error for callers while retaining
            # the exact operation handle needed for diagnosis or later resume.
            exc.operation_metadata = metadata
            raise exc
        if isinstance(exc, (TimeoutError, URLError)):
            raise FabricDefinitionPending(metadata) from exc
        raise exc
    save()
    for _ in range(12):
        try:
            with urlopen(Request(operation_url, headers=headers), timeout=20) as response:
                if response.status != 200:
                    raise ValueError("Fabric definition operation read failed")
                operation = json.loads(response.read())
                metadata['retry_after'] = response.headers.get('Retry-After',metadata.get('retry_after'))
        except (TimeoutError, URLError) as exc:
            observe_failure(exc)
        metadata['status'] = operation.get('status')
        if operation.get('error'):
            metadata['error'] = operation['error']
        save()
        if operation.get("status") == "Succeeded":
            try:
                with urlopen(Request(operation_url + "/result", headers=headers), timeout=30) as response:
                    if response.status != 200:
                        raise ValueError("Fabric definition result read failed")
                    return json.loads(response.read())
            except (TimeoutError, URLError) as exc:
                observe_failure(exc)
        if operation.get("status") not in {"NotStarted", "Running"}:
            raise ValueError("Fabric definition operation failed")
        try:
            delay=max(1,min(60,int(metadata.get('retry_after') or 1)))
        except (TypeError,ValueError):
            delay=1
        time.sleep(delay)
    raise FabricDefinitionPending(metadata)


def _private(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(PRIVATE):
        raise ValueError("all evidence paths must be under ignored private/")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--expected-definition", required=True, type=Path)
    parser.add_argument("--expected-part-count", type=int, default=9, choices=(9, 36))
    parser.add_argument("--target-scope", choices=("isolated", "report_bound"),
                        help="required for 36-part models; never infer binding scope from part count")
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--archive-dir", type=Path, help="captured committed SharePoint pages for optional exact metadata comparison")
    parser.add_argument("--validated-dir", type=Path, help="validated reconstructed metadata for optional exact metadata comparison")
    parser.add_argument("--native-fixture-readback", action="store_true",
                        help="also read back and verify all current RetentionValidation M cases")
    parser.add_argument("--expected-table", action="append", dest="expected_tables",
                        help="require terminal request objects to match this table; repeat for multi-table refreshes")
    parser.add_argument("--raw-prefix", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.expected_part_count == 36 and args.target_scope is None:
        parser.error("--target-scope is required for 36-part models")
    prefix, receipt_path, archive_path = _private(args.raw_prefix), _private(args.receipt), _private(args.archive)
    definition_path = _private(args.expected_definition)
    if bool(args.archive_dir) != bool(args.validated_dir):
        parser.error("--archive-dir and --validated-dir must be supplied together")
    metadata_dirs = (_private(args.archive_dir), _private(args.validated_dir)) if args.archive_dir else None
    if not args.dataset_id or not args.workspace_id or not args.request_id or any(c in args.dataset_id + args.workspace_id + args.request_id for c in '/?&#'):
        parser.error("workspace, dataset and request IDs must be nonempty path segments")
    raw_paths = [Path(str(prefix) + suffix) for suffix in
                 ("-refresh.json", "-keys.json", "-fields.json", "-history-before.json", "-history-after.json", "-definition-before.json", "-definition-after.json")]
    if args.native_fixture_readback:
        raw_paths.append(Path(str(prefix) + "-native-fixtures.json"))
    if len(set(raw_paths + [receipt_path, archive_path, definition_path])) != len(raw_paths) + 3:
        parser.error("archive, definition, receipt and raw evidence paths must be distinct")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    archive_bytes = archive_path.read_bytes()
    archive = retained_rows(json.loads(archive_bytes))
    expected_definition_bytes = definition_path.read_bytes()
    expected_definition = json.loads(expected_definition_bytes)
    definition_parts(expected_definition, args.expected_part_count)
    token = _token_for("https://analysis.windows.net/powerbi/api")
    dataset_root = _dataset_api_root(args.dataset_id, args.workspace_id)
    detail_url = f"{dataset_root}/refreshes/{args.request_id}"
    refresh_http, refresh = _call(detail_url, token)
    refresh_path = Path(str(prefix) + "-refresh.json")
    refresh_path.write_text(json.dumps({"http": refresh_http, "body": refresh}, indent=2) + "\n")
    disposition = refresh_disposition(refresh_http, refresh)
    if disposition != "COMPLETE":
        history_status = None
        observation_path = None
        if disposition == "WAIT":
            history_url = f"{dataset_root}/refreshes?$top=1"
            history_http, observed_history = _call(history_url, token)
            observation_path = Path(str(prefix) + "-history-observation.json")
            observation_path.write_text(json.dumps({"http": history_http, "body": observed_history}, indent=2) + "\n")
            disposition, history_status = history_disposition(history_http, observed_history, args.request_id)
        receipt = {"kind": "retained_canary_refresh_disposition_v1",
                   "status": disposition, "refresh_http": refresh_http,
                   "refresh_status": refresh.get("status") if isinstance(refresh, dict) else None,
                   "refresh_extended_status": refresh.get("extendedStatus") if isinstance(refresh, dict) else None,
                   "attempt_count": (refresh.get("numberOfAttempts") if isinstance(refresh, dict) and isinstance(refresh.get("numberOfAttempts"), int)
                                     else len(refresh["refreshAttempts"]) if isinstance(refresh, dict) and isinstance(refresh.get("refreshAttempts"), list) else None),
                   "object_count": len(refresh.get("objects", [])) if isinstance(refresh, dict) and isinstance(refresh.get("objects"), list) else None,
                   "history_status": history_status,
                   "request_id": args.request_id,
                   "raw_refresh_sha256": hashlib.sha256(refresh_path.read_bytes()).hexdigest()}
        if observation_path is not None:
            receipt["raw_history_observation_sha256"] = hashlib.sha256(observation_path.read_bytes()).hexdigest()
        if disposition in {"TERMINAL_FAILED", "ERROR"}:
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({key: value for key, value in receipt.items()
                          if key in {"status", "refresh_http", "refresh_status", "refresh_extended_status", "attempt_count", "object_count", "history_status"}}, indent=2))
        return 2 if disposition == "WAIT" else 1
    fabric_token = _token_for("https://api.fabric.microsoft.com")
    definition_before = _fabric_definition(args.workspace_id, args.dataset_id, fabric_token)
    definition_before_path = Path(str(prefix) + "-definition-before.json")
    definition_before_path.write_text(json.dumps(definition_before, indent=2) + "\n")
    definition_digest(definition_before, expected_definition, args.expected_part_count)
    # A single token and exact dataset endpoint bind both read-only queries.
    history_url = f"{dataset_root}/refreshes?$top=1"
    before_http, history_before = _call(history_url, token)
    if before_http != 200 or _latest_request(history_before) != args.request_id:
        raise ValueError("target request is not latest before the DAX reads")
    query_url = f"{dataset_root}/executeQueries"
    key_http, key_payload = _call(query_url, token, KEY_QUERY)
    field_http, field_payload = _call(query_url, token, FIELD_QUERY)
    fixture_http, fixture_payload = (None, None)
    if args.native_fixture_readback:
        fixture_http, fixture_payload = _call(query_url, token, FIXTURE_QUERY)
    metadata_payloads = {}
    if metadata_dirs:
        for source in ("PubMed", "DORA"):
            metadata_payloads[source] = _call(query_url, token, metadata_query(source))
    after_http, history_after = _call(history_url, token)
    definition_after = _fabric_definition(args.workspace_id, args.dataset_id, fabric_token)
    definition_after_path = Path(str(prefix) + "-definition-after.json")
    definition_after_path.write_text(json.dumps(definition_after, indent=2) + "\n")
    captured_at = datetime.now(timezone.utc).isoformat()
    key_path = Path(str(prefix) + "-keys.json")
    field_path = Path(str(prefix) + "-fields.json")
    key_path.write_text(json.dumps({"http": key_http, "body": key_payload}, indent=2) + "\n")
    field_path.write_text(json.dumps({"http": field_http, "body": field_payload}, indent=2) + "\n")
    fixture_path = None
    if args.native_fixture_readback:
        fixture_path = Path(str(prefix) + "-native-fixtures.json")
        fixture_path.write_text(json.dumps({"http": fixture_http, "body": fixture_payload}, indent=2) + "\n")
    metadata_paths = {}
    for source, (metadata_http, payload) in metadata_payloads.items():
        path = Path(str(prefix) + f"-{source.lower()}-metadata.json")
        path.write_text(json.dumps({"http": metadata_http, "body": payload}, indent=2) + "\n")
        metadata_paths[source] = path
    before_path = Path(str(prefix) + "-history-before.json")
    after_path = Path(str(prefix) + "-history-after.json")
    before_path.write_text(json.dumps({"http": before_http, "body": history_before}, indent=2) + "\n")
    after_path.write_text(json.dumps({"http": after_http, "body": history_after}, indent=2) + "\n")
    if key_http != 200 or field_http != 200:
        raise ValueError("both ExecuteQueries calls must return HTTP 200; raw responses retained privately")
    if args.native_fixture_readback and fixture_http != 200:
        raise ValueError("RetentionValidation ExecuteQueries call must return HTTP 200; raw response retained privately")
    if any(status != 200 for status, _ in metadata_payloads.values()):
        raise ValueError("both metadata ExecuteQueries calls must return HTTP 200; raw responses retained privately")
    if after_http != 200:
        raise ValueError("latest refresh history must return HTTP 200 after DAX reads")
    receipt = evaluate(refresh_http, refresh, history_before, history_after, args.request_id,
                       key_payload, field_payload, archive, captured_at,
                       definition_before, definition_after, expected_definition, args.expected_part_count,
                       fixture_payload=fixture_payload, target_scope=args.target_scope,
                       expected_tables=args.expected_tables)
    if metadata_dirs:
        receipt["metadata_values"] = {}
        for source, (_, payload) in metadata_payloads.items():
            source_expected = metadata_expected(*metadata_dirs, source)
            metadata_receipt, metadata_differences = verify_metadata(payload, source_expected, source)
            receipt["metadata_values"][source] = metadata_receipt
            differences_path = Path(str(prefix) + f"-{source.lower()}-metadata-differences.json")
            differences_path.write_text(json.dumps(metadata_differences, indent=2) + "\n")
            if metadata_receipt["status"] == "FAIL":
                receipt["status"] = "FAIL"
            elif metadata_receipt["status"] == "PASS_WITH_ENGINE_NORMALIZATION" and receipt["status"] == "PASS":
                receipt["status"] = "PASS_WITH_ENGINE_NORMALIZATION"
        receipt["scope"] += "; selected bibliography/raw-date values compared with validated captured archive; engine-normalized display text classified separately from substantive differences, while exact source text remains archived"
    receipt["binding"] = {
        "dataset_id": args.dataset_id,
        "workspace_id": args.workspace_id,
        "request_id": args.request_id,
        "target_scope": args.target_scope or "isolated",
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "expected_definition_sha256": hashlib.sha256(expected_definition_bytes).hexdigest(),
        "definition_before_sha256": hashlib.sha256(definition_before_path.read_bytes()).hexdigest(),
        "definition_after_sha256": hashlib.sha256(definition_after_path.read_bytes()).hexdigest(),
        "key_query_sha256": hashlib.sha256(KEY_QUERY.encode()).hexdigest(),
        "field_query_sha256": hashlib.sha256(FIELD_QUERY.encode()).hexdigest(),
        "raw_refresh_sha256": hashlib.sha256(refresh_path.read_bytes()).hexdigest(),
        "raw_keys_sha256": hashlib.sha256(key_path.read_bytes()).hexdigest(),
        "raw_fields_sha256": hashlib.sha256(field_path.read_bytes()).hexdigest(),
        "history_before_sha256": hashlib.sha256(before_path.read_bytes()).hexdigest(),
        "history_after_sha256": hashlib.sha256(after_path.read_bytes()).hexdigest(),
    }
    if fixture_path is not None:
        receipt["binding"]["native_fixture_query_sha256"] = hashlib.sha256(FIXTURE_QUERY.encode()).hexdigest()
        receipt["binding"]["raw_native_fixture_sha256"] = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    if metadata_dirs:
        receipt["binding"]["validated_receipt_sha256"] = hashlib.sha256((metadata_dirs[1] / "validated-receipt.json").read_bytes()).hexdigest()
        for source, path in metadata_paths.items():
            receipt["binding"][f"{source.lower()}_metadata_query_sha256"] = hashlib.sha256(metadata_query(source).encode()).hexdigest()
            receipt["binding"][f"raw_{source.lower()}_metadata_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "key_parity": receipt["key_parity"]["counts"],
                      "field_integrity": receipt["field_integrity"]["counts"],
                      "native_fixture_validation": receipt.get("native_fixture_validation", {}).get("counts"),
                      "metadata_values": {source: {"status": result["status"], "differences": result["differences"]}
                                          for source, result in receipt.get("metadata_values", {}).items()}}, indent=2))
    return 0 if receipt["status"] in {"PASS", "PASS_WITH_ENGINE_NORMALIZATION"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
