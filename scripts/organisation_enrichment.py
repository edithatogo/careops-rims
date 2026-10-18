"""Evidence-preserving organisational enrichment for publication records.

Matches explicit affiliation text to a versioned organisation reference. It does
not infer an organisation from author names, titles, locality, or journal.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE = ROOT / "config" / "organisation-hierarchy.json"


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def load_reference(path: Path = DEFAULT_REFERENCE) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = str(payload.get("version") or "").strip()
    if not version:
        raise ValueError("organisation reference requires version")
    def valid_date(value: Any, label: str) -> str:
        text = str(value or "").strip()
        if text:
            try:
                date.fromisoformat(text)
            except ValueError as exc:
                raise ValueError(f"{label} must be ISO date") from exc
        return text

    valid_date(payload.get("effective_from"), "reference effective_from")
    valid_date(payload.get("effective_to"), "reference effective_to")
    result = {}
    for unit in payload.get("units", []):
        if not unit.get("OrganisationKey") or not unit.get("OrganisationName"):
            raise ValueError("organisation unit requires key and name")
        key = unit["OrganisationKey"]
        if key in result:
            raise ValueError(f"duplicate organisation key: {key}")
        aliases = [unit["OrganisationName"], *unit.get("Aliases", [])]
        normalised = list(dict.fromkeys(_norm(a) for a in aliases if _norm(a)))
        effective_from = valid_date(unit.get("EffectiveFrom") or payload.get("effective_from"), f"{key} EffectiveFrom")
        effective_to = valid_date(unit.get("EffectiveTo") or payload.get("effective_to"), f"{key} EffectiveTo")
        result[key] = {
            **unit,
            "_aliases": normalised,
            "_reference_version": version,
            "_effective_from": effective_from,
            "_effective_to": effective_to,
        }
    for key, unit in result.items():
        parent = unit.get("ParentOrganisationKey")
        if parent and parent not in result:
            raise ValueError(f"organisation {key} has unknown parent {parent}")
    return result


def enrich_record(record: dict[str, Any], reference: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    reference = reference or load_reference()
    affiliation = record.get("Affiliations") or record.get("AuthorAffiliations") or record.get("AffiliationText") or ""
    text = _norm(affiliation)
    matches = []
    evidence = []
    for key, unit in reference.items():
        aliases = sorted(
            (a for a in unit["_aliases"] if re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", text)),
            key=len,
            reverse=True,
        )
        if aliases:
            matches.append(key)
            evidence.append(f"{unit['OrganisationName']}: {aliases[0]}")
    matches = sorted(set(matches))
    record["OrganisationKeys"] = ";".join(matches)
    record["OrganisationNames"] = ";".join(reference[k]["OrganisationName"] for k in matches)
    record["OrganisationMatchMethod"] = "explicit-affiliation-alias" if matches else "unmatched"
    record["OrganisationMatchConfidence"] = "high" if matches else "unknown"
    record["OrganisationEvidence"] = "; ".join(sorted(set(evidence)))
    record["AffiliationTextObserved"] = str(affiliation)
    record["OrganisationReferenceVersion"] = next(iter(reference.values()), {}).get("_reference_version", "") if reference else ""
    record["OrganisationEffectiveFrom"] = ";".join(sorted({reference[k]["_effective_from"] for k in matches if reference[k]["_effective_from"]}))
    record["OrganisationEffectiveTo"] = ";".join(sorted({reference[k]["_effective_to"] for k in matches if reference[k]["_effective_to"]}))
    return record
