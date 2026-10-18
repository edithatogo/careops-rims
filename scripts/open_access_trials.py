"""Open Access compliance and Clinical Trial Registry linkage.

Deterministic, keyless processing for:
1. Open Access category classification (Gold, Hybrid, Green, Bronze, Closed)
2. NHMRC / MRFF Open Access Policy 2022 compliance determination
3. ANZCTR (ACTRN...) and ClinicalTrials.gov (NCT...) identification and URL resolution
"""
from __future__ import annotations

import re
from typing import Any

ANZCTR_PATTERN = re.compile(r"\bACTRN\d{14}\b", re.IGNORECASE)
NCT_PATTERN = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)


def classify_open_access_status(
    oa_status: str | None,
    license_str: str | None = None,
    is_oa: bool | None = None,
) -> tuple[str, str]:
    """Classify Open Access category and NHMRC mandate compliance.

    Returns:
        (category, compliance_status)
        Categories: 'Gold', 'Hybrid', 'Green', 'Bronze', 'Closed', 'Unknown'
        Compliance: 'Fully Compliant', 'Conditionally Compliant', 'Non-Compliant', 'Unknown'
    """
    status_lower = str(oa_status or "").strip().lower()
    lic_lower = str(license_str or "").strip().lower()

    if is_oa is False or status_lower == "closed":
        return ("Closed", "Non-Compliant")

    if "gold" in status_lower:
        return ("Gold", "Fully Compliant")
    if "hybrid" in status_lower:
        return ("Hybrid", "Fully Compliant")
    if "green" in status_lower:
        return ("Green", "Fully Compliant")
    if "bronze" in status_lower:
        return ("Bronze", "Conditionally Compliant")

    # If status is simply "open" or unknown, infer from license
    if "cc-by" in lic_lower or "creative commons attribution" in lic_lower:
        return ("Gold", "Fully Compliant")
    if "cc-by-nc" in lic_lower or "cc by" in lic_lower:
        return ("Hybrid", "Fully Compliant")

    if is_oa is True or status_lower in ("open", "oa"):
        # Without specific license or repo flag, free-to-read is treated as Bronze
        return ("Bronze", "Conditionally Compliant")

    return ("Unknown", "Unknown")


def extract_trial_registrations(text: str | None) -> list[dict[str, str]]:
    """Extract ANZCTR and ClinicalTrials.gov registration IDs and generate verified URLs."""
    if not text:
        return []

    results: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for m in ANZCTR_PATTERN.finditer(str(text)):
        trial_id = m.group(0).upper()
        if trial_id not in seen_ids:
            seen_ids.add(trial_id)
            results.append({
                "registry": "ANZCTR",
                "trial_id": trial_id,
                "trial_url": f"https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id={trial_id}",
            })

    for m in NCT_PATTERN.finditer(str(text)):
        trial_id = m.group(0).upper()
        if trial_id not in seen_ids:
            seen_ids.add(trial_id)
            results.append({
                "registry": "ClinicalTrials.gov",
                "trial_id": trial_id,
                "trial_url": f"https://clinicaltrials.gov/study/{trial_id}",
            })

    return results


def format_trial_registry_summary(trials: list[dict[str, str]]) -> tuple[str | None, str | None]:
    """Format trial registrations into semicolon-separated ID and URL strings."""
    if not trials:
        return (None, None)
    ids = "; ".join(t["trial_id"] for t in trials)
    urls = "; ".join(t["trial_url"] for t in trials)
    return (ids, urls)


def enrich_record_open_access_trials(record: dict[str, Any]) -> dict[str, Any]:
    """Enrich a publication record with OA status, NHMRC compliance, and trial links."""
    oa_status = record.get("OpenAccessStatus") or record.get("EuropePMC_OpenAccess")
    lic = record.get("License") or record.get("OALicense")
    is_oa = record.get("IsOpenAccess")

    category, compliance = classify_open_access_status(oa_status, license_str=lic, is_oa=is_oa)
    record["OACategory"] = category
    record["OAComplianceNHMRC"] = compliance

    corpus = f"{record.get('Title', '')} {record.get('AttributionEvidence', '')} {record.get('MeSHHeadings', '')} {record.get('ClinicalTrialID', '')}"
    trials = extract_trial_registrations(corpus)
    t_ids, t_urls = format_trial_registry_summary(trials)
    if t_ids:
        record["TrialRegistryID"] = t_ids
        record["TrialRegistryURL"] = t_urls
    else:
        record.setdefault("TrialRegistryID", None)
        record.setdefault("TrialRegistryURL", None)

    return record
