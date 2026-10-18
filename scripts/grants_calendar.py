"""Build a review-gated iCalendar projection for grant opportunities.

The output is a local artifact contract.  It does not subscribe users, send
notifications, or write a calendar.  Only exact source deadlines or valid
institutional dates become events; uncertain dates are omitted rather than
assigned a guessed day.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from scripts.grants_planning import institutional_deadline, validate_policy


def _escape(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "\\n").replace("\n", "\\n")


def _date(value: Any) -> str | None:
    if not isinstance(value, str):
        raise ValueError("calendar opportunity Deadline must be a string for day precision")
    raw = value
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise ValueError("calendar opportunity Deadline must be an ISO date for day precision")
    try:
        dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("calendar opportunity Deadline is not a valid date") from exc
    return raw


def _valid_http_url(value: Any) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def event_uid(opportunity_key: str, anchor: str, policy_key: str, policy_version: str) -> str:
    basis = "|".join((opportunity_key, anchor, policy_key, policy_version))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32] + "@chhhs-rims"


def project_event(opportunity: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any] | None:
    """Project one opportunity to an all-day event, or return None if uncertain."""
    if not validate_policy(policy):
        raise ValueError("invalid institutional policy")
    if not isinstance(opportunity, dict):
        raise ValueError("calendar opportunity must be an object")
    precision = opportunity.get("DeadlinePrecision")
    if precision is not None and not isinstance(precision, str):
        raise ValueError("calendar opportunity DeadlinePrecision must be a string")
    for field in ("Title", "Source", "Status"):
        if field in opportunity and not isinstance(opportunity[field], str):
            raise ValueError(f"calendar opportunity {field} must be a string")
    source_date = _date(opportunity.get("Deadline")) if precision == "day" else None
    if source_date is None:
        return None
    for field in ("OpportunityKey", "URL"):
        if field not in opportunity or opportunity[field] is None or opportunity[field] == "":
            raise ValueError(f"calendar opportunity missing {field}")
        if not isinstance(opportunity[field], str) or not opportunity[field].strip():
            raise ValueError(f"calendar opportunity {field} must be a string")
        if opportunity[field] != opportunity[field].strip():
            raise ValueError(f"calendar opportunity {field} must not have surrounding whitespace")
    anchor = "institutional"
    event_date = institutional_deadline(
        source_date,
        policy["LeadDays"],
        business_days=policy["CalendarOrBusinessDays"] == "business",
        holidays=policy.get("HolidayDates", ()),
    ) if source_date is not None else None
    if event_date is None:
        return None
    opportunity_key = opportunity["OpportunityKey"]
    url = opportunity["URL"]
    if not _valid_http_url(url):
        raise ValueError("calendar opportunity requires an HTTP(S) URL")
    status = str(opportunity.get("Status") or "Unknown")
    event_status = "CANCELLED" if status.casefold() in {"cancelled", "canceled"} else "TENTATIVE"
    return {
        "UID": event_uid(opportunity_key, anchor, policy["PolicyKey"], policy["Version"]),
        "Date": event_date, "Status": event_status, "Anchor": anchor,
        "Title": str(opportunity.get("Title") or "Grant opportunity"),
        "URL": url, "Source": str(opportunity.get("Source") or ""),
        "OpportunityKey": opportunity_key, "PolicyKey": str(policy["PolicyKey"]),
        "PolicyVersion": str(policy["Version"]), "ExternalDeadline": source_date,
    }


def build_icalendar(opportunities: Iterable[dict[str, Any]], policy: dict[str, Any], *, generated_utc: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", generated_utc):
        raise ValueError("generated_utc must be second-precision UTC")
    try:
        dt.datetime.strptime(generated_utc, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValueError("generated_utc must be a valid UTC timestamp") from None
    events = [project_event(item, policy) for item in opportunities]
    events = sorted((item for item in events if item is not None), key=lambda item: (item["Date"], item["UID"]))
    uids = [event["UID"] for event in events]
    if len(uids) != len(set(uids)):
        raise ValueError("duplicate calendar event UID")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CHHHS RIMS//Grant Calendar//EN", "CALSCALE:GREGORIAN", f"DTSTAMP:{generated_utc.replace('-', '').replace(':', '')}"]
    for event in events:
        next_day = (dt.date.fromisoformat(event["Date"]) + dt.timedelta(days=1)).strftime("%Y%m%d")
        lines.extend(["BEGIN:VEVENT", f"UID:{event['UID']}", f"DTSTART;VALUE=DATE:{event['Date'].replace('-', '')}", f"DTEND;VALUE=DATE:{next_day}", f"SUMMARY:{_escape(event['Title'])}", f"STATUS:{event['Status']}", f"CATEGORIES:{_escape(event['Source']) or 'Grant'}", f"DESCRIPTION:{_escape('Institutional planning anchor: ' + event['Anchor'] + '; OpportunityKey: ' + event['OpportunityKey'])}", f"URL:{_escape(event['URL'])}", "END:VEVENT"])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("opportunities", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--generated-utc", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = build_icalendar(json.loads(args.opportunities.read_text()), json.loads(args.policy.read_text()), generated_utc=args.generated_utc)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(output, encoding="utf-8", newline="")


if __name__ == "__main__":
    main()
