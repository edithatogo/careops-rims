"""Clinical attribution, ANZSRC Fields of Research (FoR), and specialty classification.

Provides deterministic, keyless classification for:
1. Authorship Leadership (Cairns-Led vs Collaborative vs Unattributed)
2. ANZSRC 2020 Fields of Research Division (e.g. 32 Biomedical & Clinical Sciences)
3. Hospital Clinical Directorate Service Lines (e.g. Infectious Diseases, Cancer Care)
"""
from __future__ import annotations

import re
from typing import Any

CAIRNS_FACILITY_KEYWORDS = [
    "cairns hospital",
    "cairns & hinterland",
    "cairns and hinterland",
    "chhhs",
    "atherton hospital",
    "innisfail hospital",
    "mareeba hospital",
    "mossman hospital",
    "yarrabah",
    "babinda hospital",
    "herberton hospital",
    "gordonvale hospital",
]


def _is_cairns_affiliation(text: str | None) -> bool:
    if not text:
        return False
    t = str(text).lower()
    return any(k in t for k in CAIRNS_FACILITY_KEYWORDS)


def classify_authorship_leadership(
    authors: str | None,
    affiliations: str | None = None,
    author_affiliations: list[dict[str, Any]] | None = None,
    matched_facilities: str | None = None,
) -> str:
    """Determine whether CHHHS is lead author (first or senior) or collaborator.

    Categories:
    - 'Cairns-Led': First author or last (senior) author affiliated with CHHHS / Cairns Hospital.
    - 'Collaborative': Middle co-author affiliated with CHHHS / Cairns Hospital.
    - 'Unattributed': No detectable CHHHS affiliation.
    """
    if not authors or not str(authors).strip():
        return "Unattributed"

    # Semicolon/newline delimiters are the only reliable separators here;
    # comma is commonly part of ``Surname, Given`` display names.
    author_list = [a.strip() for a in re.split(r";|\n", str(authors)) if a.strip()]
    if not author_list:
        return "Unattributed"

    # Case A: Structured list of author-affiliation dicts
    if author_affiliations and isinstance(author_affiliations, list):
        if not author_affiliations:
            return "Unattributed"
        # List order is not evidence of author order unless the source explicitly
        # supplies an order/role marker. Preserve the affiliation evidence but do
        # not promote an unordered match to leadership.
        explicit_first = [item for item in author_affiliations if item.get("is_first_author") is True or item.get("author_role") == "first"]
        explicit_last = [item for item in author_affiliations if item.get("is_last_author") is True or item.get("author_role") in {"last", "senior"}]
        if any(_is_cairns_affiliation(item.get("affiliation", "")) for item in explicit_first + explicit_last):
            return "Cairns-Led"

        if any(_is_cairns_affiliation(item.get("affiliation", "")) for item in author_affiliations):
            return "Collaborative"

        return "Unattributed"

    # Case B: Single author
    if len(author_list) <= 1:
        if _is_cairns_affiliation(affiliations) or (matched_facilities and matched_facilities.strip()):
            return "Cairns-Led"
        return "Unattributed"

    # Case C: Free-text affiliations string
    if affiliations:
        aff_text = str(affiliations).lower()
        if not _is_cairns_affiliation(aff_text):
            return "Unattributed"

        # Check for numbered affiliation pattern (e.g., "1: Cairns Hospital", "3: Cairns Hospital")
        first_author_patterns = [r"\b1\s*[:\.]\s*[^;]*cairns", r"first author[^;]*cairns"]
        last_idx = len(author_list)
        last_author_patterns = [
            rf"\b{last_idx}\s*[:\.]\s*[^;]*cairns",
            r"senior author[^;]*cairns",
            r"last author[^;]*cairns",
        ]

        if any(re.search(pat, aff_text) for pat in first_author_patterns) or any(
            re.search(pat, aff_text) for pat in last_author_patterns
        ):
            return "Cairns-Led"

        return "Collaborative"

    if matched_facilities and matched_facilities.strip():
        return "Collaborative"

    return "Unattributed"


def classify_anzsrc_for(
    title: str | None = None,
    mesh: str | None = None,
    journal: str | None = None,
    concepts: str | None = None,
) -> tuple[str, str]:
    """Map publication to ANZSRC 2020 Fields of Research 2-digit Division.

    Returns:
        tuple of (DivisionCode, DivisionTitle)
    """
    corpus = f"{title or ''} {mesh or ''} {journal or ''} {concepts or ''}".lower()

    # Division 31: Biological Sciences
    if any(k in corpus for k in [
        "phylogen", "fungal genetics", "molecular evolution", "taxonomy",
        "botany", "zoology", "ecology, evolutionary", "genome, fungal",
    ]):
        return ("31", "Biological Sciences")

    # Division 41: Environmental Sciences
    if any(k in corpus for k in [
        "environmental health", "vector biology", "climate change",
        "water quality", "toxicology, environmental", "air pollution"
    ]):
        return ("41", "Environmental Sciences")

    # Division 42: Health Sciences
    if any(k in corpus for k in [
        "nursing", "allied health", "physiotherapy", "occupational therapy",
        "health services", "health policy", "health systems", "patient discharge",
        "workload", "hospital discharge", "health service research"
    ]):
        return ("42", "Health Sciences")

    # Division 44: Human Society
    if any(k in corpus for k in [
        "medical anthropology", "health sociology", "criminology", "social policy"
    ]):
        return ("44", "Human Society")

    # Division 52: Psychology
    if any(k in corpus for k in [
        "psychology", "cognitive psychology", "behavioral sciences", "psychotherapy"
    ]):
        return ("52", "Psychology")

    # Default for acute hospital peer-reviewed clinical research: Division 32
    return ("32", "Biomedical and Clinical Sciences")


def classify_clinical_specialty(
    title: str | None = None,
    mesh: str | None = None,
    journal: str | None = None,
    department: str | None = None,
) -> str:
    """Map publication to CHHHS Clinical Directorate Service Line."""
    corpus = f"{title or ''} {mesh or ''} {journal or ''} {department or ''}".lower()

    # 1. Infectious Diseases & Tropical Health
    if any(k in corpus for k in [
        "infectious", "infection", "tropical", "melioidosis", "dengue",
        "malaria", "tuberculosis", "hiv", "covid", "sars-cov-2", "microbiol",
        "antimicrobial", "sepsis", "bacter", "virol", "burkholderia"
    ]):
        return "Infectious Diseases & Tropical Health"

    # 2. Emergency & Critical Care
    if any(k in corpus for k in [
        "emergency", "resuscitation", "intensive care", "critical care",
        "trauma", "retrieval", "high-flow", "respiratory failure", "cardiac arrest"
    ]) or re.search(r"\bicu\b", corpus):
        return "Emergency & Critical Care"

    # 3. Cancer Care
    if any(k in corpus for k in [
        "oncology", "cancer", "carcinoma", "melanoma", "tumour", "tumor",
        "chemotherapy", "radiation oncology", "leukaemia", "leukemia",
        "lymphoma", "palliative"
    ]):
        return "Cancer Care"

    # 4. Women's and Child Health
    if any(k in corpus for k in [
        "paediatr", "pediatr", "child", "infant", "neonat", "obstetric",
        "gynaecol", "gynecol", "maternal", "pregnancy", "fetal", "scbu"
    ]):
        return "Women's and Child Health"

    # 5. Surgical Specialties
    if any(k in corpus for k in [
        "surgery", "surgical", "orthop", "fracture", "arthroplasty",
        "ophthalmol", "urol", "vascular surgery", "neurosurger",
        "otolaryng", "ear, nose"
    ]) or re.search(r"\bent\b", corpus):
        return "Surgical Specialties"

    # 6. Mental Health & Addictions
    if any(k in corpus for k in [
        "psychiat", "mental health", "depression", "schizophrenia",
        "psychosis", "addiction", "substance use", "alcohol"
    ]):
        return "Mental Health & Addictions"

    # 7. Allied Health & Nursing
    if any(k in corpus for k in [
        "nursing", "physiotherapy", "speech pathol", "dietetics", "nutrition",
        "occupational therapy", "pharmacy", "pharmacist", "social work"
    ]):
        return "Allied Health & Nursing"

    # 8. Medical Specialties (Default for internal medicine, cardiology, renal, neurology, etc.)
    return "Medical Specialties"


def enrich_record_clinical_attribution(record: dict[str, Any]) -> dict[str, Any]:
    """Enrich a publication record with leadership role, FoR code/division, and specialty."""
    authors = record.get("Authors") or record.get("AuthorList") or ""
    affiliations = record.get("Affiliations") or record.get("AuthorAffiliations") or ""
    matched_facilities = record.get("MatchedFacilities") or ""
    title = record.get("Title") or ""
    mesh = record.get("MeSHTerms") or record.get("MeshHeadings") or ""
    journal = record.get("Journal") or record.get("SourceTitle") or ""
    department = record.get("Department") or ""

    record["LeadershipRole"] = classify_authorship_leadership(
        authors=authors,
        affiliations=str(affiliations) if affiliations else None,
        matched_facilities=matched_facilities,
    )
    for_code, for_division = classify_anzsrc_for(
        title=title,
        mesh=mesh,
        journal=journal,
    )
    record["ANZSRCFoRCode"] = for_code
    record["ANZSRCFoRDivision"] = for_division
    record["ClinicalSpecialty"] = classify_clinical_specialty(
        title=title,
        mesh=mesh,
        journal=journal,
        department=department,
    )
    return record
