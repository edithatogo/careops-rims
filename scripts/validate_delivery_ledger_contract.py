"""Validate the current-user Funding Delivery Ledger schema contract."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "config" / "funding-delivery-ledger.schema.json"


def main() -> int:
    data = json.loads(SCHEMA.read_text())
    required = {
        "DeliveryEventKey", "UserKey", "OpportunityKey", "EventType",
        "Revision", "OffsetDays", "Channel", "Status", "ScheduledFor",
        "SentAt", "ErrorMessage",
    }
    fields = {field["display_name"]: field for field in data["fields"]}
    errors = []
    if data.get("schema_version") != "funding-delivery-ledger-v1":
        errors.append("unexpected schema version")
    if data.get("identity_field") != "DeliveryEventKey":
        errors.append("identity field must be DeliveryEventKey")
    if set(fields) != required:
        errors.append(f"field set mismatch: {sorted(set(fields) ^ required)}")
    identity = fields.get("DeliveryEventKey", {})
    if not identity.get("required") or not identity.get("unique"):
        errors.append("DeliveryEventKey must be required and unique")
    if fields.get("OffsetDays", {}).get("type") != "integer":
        errors.append("OffsetDays must be an integer")
    for name in ("UserKey", "OpportunityKey", "EventType", "Revision", "Channel", "Status"):
        if not fields.get(name, {}).get("required"):
            errors.append(f"{name} must be required")
    if fields.get("Status", {}).get("default") != "Pending":
        errors.append("Status must default to Pending")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: funding delivery ledger schema contract is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
