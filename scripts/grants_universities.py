"""Validate university source and institutional-deadline discovery records."""
from __future__ import annotations

import json
import math
from pathlib import Path
from datetime import date, datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

REQUIRED_INSTITUTIONS = {"jcu", "uq", "qut", "griffith"}
CATALOGUE_TIMEZONE = ZoneInfo("Australia/Brisbane")


def _validate_lead_time(value, key):
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"institution {key!r} internal_lead_time must be an object or null")
    if value.get("unit") not in {"business_days", "working_days", "calendar_days"}:
        raise ValueError(f"institution {key!r} has unsupported lead-time unit")
    raw_values = [item for name, item in value.items() if name != "unit"]
    if any(isinstance(item, bool) for item in raw_values):
        raise ValueError(f"institution {key!r} has an invalid lead-time value")
    numeric_values = [item for item in raw_values if isinstance(item, (int, float))]
    if not numeric_values:
        raise ValueError(f"institution {key!r} needs a numeric lead-time value")
    if any(not isinstance(item, int) for item in numeric_values):
        raise ValueError(f"institution {key!r} has a non-integral lead-time value")
    if any(not math.isfinite(item) or item < 0 or item > 3660 for item in numeric_values):
        raise ValueError(f"institution {key!r} has an invalid lead-time value")


def _valid_http_url(value):
    if not isinstance(value, str) or value != value.strip():
        return False
    parsed = urlsplit(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_universities(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("university catalogue must be a list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("university catalogue rows must be objects")
        raw_key = row.get("institution_id")
        if not isinstance(raw_key, str):
            raise ValueError("institution_id must be a non-empty string")
        key = raw_key.strip()
        if not key or key in seen:
            raise ValueError(f"duplicate or missing institution_id: {key!r}")
        if key != raw_key:
            raise ValueError(f"institution {key!r} must not have surrounding whitespace")
        seen.add(key)
        for field in ("name", "authority_url", "access", "format", "intake", "eligibility_scope", "policy_note", "last_verified"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"institution {key!r} needs {field}")
        if not _valid_http_url(row["authority_url"]):
            raise ValueError(f"institution {key!r} needs a valid authority URL")
        try:
            verified = date.fromisoformat(row["last_verified"])
        except ValueError:
            raise ValueError(f"institution {key!r} has an invalid last_verified date") from None
        if verified > datetime.now(CATALOGUE_TIMEZONE).date():
            raise ValueError(f"institution {key!r} has a future last_verified date")
        _validate_lead_time(row.get("internal_lead_time"), key)
        if row["intake"] != "manual_review":
            raise ValueError(f"institution {key!r} must remain manual_review until access is proven")
    missing = REQUIRED_INSTITUTIONS - seen
    if missing:
        raise ValueError(f"required universities missing: {sorted(missing)}")
    return rows


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("catalogue", type=Path)
    args = parser.parse_args()
    print(f"validated {len(load_universities(args.catalogue))} university rows")
