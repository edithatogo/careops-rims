"""Deterministic keyless classifiers for CHHHS research governance.

Provides rule-based classification for:
1. FundingType (Commonwealth, State, Philanthropic, Industry, University, Unfunded)
2. IsInternalFunding (CHHHS / Cairns Hospital Foundation / SERTA)
3. IndigenousHealthFocus (FNQ First Nations health relevance via MeSH and keywords)
4. StudyDesign (Evidence hierarchy via MeSH / PublicationType)
5. ClinicalTrialID (ANZCTR and ClinicalTrials.gov regex extraction)

Requires zero external API keys or tokens. Runs purely on harvested metadata.
"""
from __future__ import annotations

import re
from typing import Any


def classify_funding_type(funder_names: str | None) -> str:
    """Classify funding bodies into standardized governance categories."""
    if not funder_names or not str(funder_names).strip():
        return "Unfunded / Departmental"

    fn = str(funder_names).lower().strip()

    # Commonwealth competitive schemes
    if any(k in fn for k in [
        "nhmrc", "national health and medical research", "mrff",
        "medical research future fund", "australian research council",
        "commonwealth", "department of health, australian government"
    ]) or re.search(r'\barc\b', fn):
        return "Commonwealth (NHMRC/MRFF)"

    # State & Queensland Health schemes
    if any(k in fn for k in [
        "queensland health", "qld health", "health department",
        "state health", "state health research advisory", "junior doctor research fellowship"
    ]):
        return "State / Qld Health"

    # Philanthropic & Medical Research Foundations
    if any(k in fn for k in [
        "cairns hospital foundation", "emergency medicine foundation",
        "royal brisbane", "foundation", "trust", "endowment", "gates foundation",
        "wellcome", "alfred hospital research trust", "green lane research"
    ]):
        return "Philanthropic / Foundation"

    # Commercial & Pharmaceutical Industry Sponsors
    if any(k in fn for k in [
        "novartis", "pfizer", "merck", "roche", "astrazeneca",
        "gilead", "bms", "bristol-myers", "sanofi", "glaxosmithkline", "gsk", "eli lilly"
    ]):
        return "Commercial / Industry Trial"

    # Academic & University Partners
    if any(k in fn for k in [
        "university", "college", "institute", "jcu", "james cook", "sydney medical school"
    ]):
        return "University Partner"

    return "Other External Funder"


def is_internal_funding(funder_names: str | None, attribution_evidence: str | None = None) -> bool:
    """Flag publications funded by internal CHHHS / Cairns Hospital Foundation / SERTA trust."""
    combined = f"{funder_names or ''} {attribution_evidence or ''}".lower()
    return any(k in combined for k in [
        "cairns hospital foundation",
        "serta",
        "study, education and research trust",
        "chhhs research grant",
        "cairns and hinterland health and medical research grant",
    ])


def classify_indigenous_health_focus(
    mesh: str | None = None,
    keywords: str | None = None,
    title: str | None = None,
) -> bool:
    """Identify publications addressing First Nations health equity in Far North Queensland."""
    corpus = f"{mesh or ''} {keywords or ''} {title or ''}".lower()
    return any(k in corpus for k in [
        "oceanic ancestry group",
        "health services, indigenous",
        "indigenous",
        "first nations",
        "aboriginal",
        "torres strait",
        "cape york",
    ])


def classify_study_design(
    mesh: str | None = None,
    publication_types: str | None = None,
    title: str | None = None,
) -> str:
    """Classify the clinical study design / evidence level from MeSH, types, and title."""
    corpus = f"{mesh or ''} {publication_types or ''} {title or ''}".lower()

    if any(k in corpus for k in ["systematic review", "meta-analysis"]):
        return "Systematic Review / Meta-Analysis"
    if any(k in corpus for k in ["randomized controlled trial", "randomised controlled trial", "clinical trial"]):
        return "Randomized Controlled Trial"
    if any(k in corpus for k in ["guideline", "practice guideline", "consensus statement"]):
        return "Clinical Practice Guideline"
    if any(k in corpus for k in ["cohort", "prospective", "retrospective", "case-control", "observational"]):
        return "Observational / Cohort Study"
    if any(k in corpus for k in ["case report", "case reports"]):
        return "Case Report"

    return "Other Biomedical / Translational"


def extract_clinical_trial_ids(text: str | None) -> str | None:
    """Extract ANZCTR (ACTRN...) and ClinicalTrials.gov (NCT...) registry numbers."""
    if not text:
        return None
    matches = []
    # ANZCTR: ACTRN followed by 14 digits
    for m in re.finditer(r'ACTRN\d{14}', text, re.I):
        val = m.group(0).upper()
        if val not in matches:
            matches.append(val)
    # ClinicalTrials.gov: NCT followed by 8 digits
    for m in re.finditer(r'NCT\d{8}', text, re.I):
        val = m.group(0).upper()
        if val not in matches:
            matches.append(val)

    return "; ".join(matches) if matches else None
