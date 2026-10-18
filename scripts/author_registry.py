"""Build a conservative, derived author registry from retained source evidence.

This module deliberately does not harvest ResearchGate or promote name-only
matches. It creates auditable author-publication relationships and statistics
for review and reporting.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Iterable


IDENTIFIER_FIELDS = ("ORCID", "AuthorORCID", "OpenAlexAuthorID", "ScopusAuthorID", "WoSResearcherID")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalise_name(value: Any) -> str:
    """Return a comparison form without changing the displayed name."""
    return re.sub(r"[^a-z0-9]", "", _clean(value).casefold())


def author_key(name: Any, identifier: Any = None) -> str:
    """Create a stable non-semantic key; identifiers prevent same-name merging."""
    basis = _clean(identifier) or f"name:{normalise_name(name)}"
    return "AUTH:" + hashlib.sha256(basis.casefold().encode("utf-8")).hexdigest()[:24]


def identity_status(identifier: Any = None, affiliation: Any = None) -> str:
    if _clean(identifier):
        return "Confirmed"
    if _clean(affiliation):
        return "Probable"
    return "Unresolved"


def _identifier(row: dict[str, Any]) -> str:
    for field in IDENTIFIER_FIELDS:
        if _clean(row.get(field)):
            return _clean(row[field])
    return ""


def build_author_registry(
    pubmed_author_rows: Iterable[dict[str, Any]] = (),
    dora_records: Iterable[dict[str, Any]] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(authors, evidence)`` from structured PubMed and DORA records.

    PubMed rows should contain PMID, AuthorIndex, AuthorName, AffiliationText,
    AffiliationIndex and EvidenceKind. DORA records may contain DORAKey,
    Authors, DORAURL, CHHHSAffiliatedAuthors and AttributionEvidence.
    """
    authors: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []

    def add(name: Any, source: str, publication_key: str, row: dict[str, Any], order: int, affiliation: str = "") -> None:
        display = _clean(name)
        if not display or not publication_key:
            return
        identifier = _identifier(row)
        key = author_key(display, identifier)
        status = identity_status(identifier, affiliation)
        record = authors.setdefault(key, {
            "AuthorKey": key,
            "DisplayName": display,
            "NameVariants": display,
            "IdentityStatus": status,
            "IdentityConfidence": "high" if identifier else ("medium" if affiliation else "low"),
            "ExternalIdentifiers": identifier,
            "PublicationCount": 0,
            "FirstAuthorCount": 0,
            "SeniorAuthorCount": 0,
            "CollaborativeCount": 0,
            "Sources": set(),
        })
        if display not in record["NameVariants"].split("; "):
            record["NameVariants"] += "; " + display
        if status == "Confirmed" or record["IdentityStatus"] == "Unresolved":
            record["IdentityStatus"] = status
            record["IdentityConfidence"] = "high" if status == "Confirmed" else record["IdentityConfidence"]
        record["Sources"].add(source)
        relation = {
            "AuthorKey": key,
            "Source": source,
            "SourceKey": f"{source.lower()}:{publication_key}",
            "AuthorName": display,
            "AuthorOrder": order,
            "AffiliationText": affiliation,
            "AffiliationIndex": row.get("AffiliationIndex"),
            "EvidenceKind": _clean(row.get("EvidenceKind")) or ("DORA attribution text" if source == "DORA" else "author record"),
            "EvidenceURL": _clean(row.get("DORAURL")),
            "AttributionEvidence": _clean(row.get("AttributionEvidence")),
            "ReviewStatus": "Needs Review" if status in {"Candidate", "Unresolved"} else "Needs Review",
        }
        evidence.append(relation)

    for row in pubmed_author_rows:
        row = dict(row)
        add(row.get("AuthorName"), "PubMed", _clean(row.get("PMID")), row, int(row.get("AuthorIndex") or 0), _clean(row.get("AffiliationText")))

    for row in dora_records:
        row = dict(row)
        names = [n.strip() for n in re.split(r";|\n", _clean(row.get("Authors"))) if n.strip()]
        for index, name in enumerate(names, 1):
            add(name, "DORA", _clean(row.get("DORAKey")), row, index, _clean(row.get("AttributionEvidence")) or _clean(row.get("CHHHSAffiliatedAuthors")))

    for record in authors.values():
        record["Sources"] = "; ".join(sorted(record["Sources"]))
        record["PublicationCount"] = len({r["SourceKey"] for r in evidence if r["AuthorKey"] == record["AuthorKey"]})
        related = [r for r in evidence if r["AuthorKey"] == record["AuthorKey"]]
        record["FirstAuthorCount"] = sum(r["AuthorOrder"] == 1 for r in related)
        record["SeniorAuthorCount"] = sum(r["AuthorOrder"] == max(x["AuthorOrder"] for x in related) for r in related)
        record["CollaborativeCount"] = max(0, record["PublicationCount"] - record["FirstAuthorCount"] - record["SeniorAuthorCount"] + sum(r["AuthorOrder"] == 1 and r["AuthorOrder"] == max(x["AuthorOrder"] for x in related) for r in related))
    return sorted(authors.values(), key=lambda r: r["DisplayName"].casefold()), evidence


def author_statistics(authors: Iterable[dict[str, Any]], evidence: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarise the derived registry without inventing completeness."""
    authors = list(authors)
    evidence = list(evidence)
    return {
        "AuthorCount": len(authors),
        "RelationshipCount": len(evidence),
        "ConfirmedAuthorCount": sum(a.get("IdentityStatus") == "Confirmed" for a in authors),
        "ProbableAuthorCount": sum(a.get("IdentityStatus") == "Probable" for a in authors),
        "UnresolvedAuthorCount": sum(a.get("IdentityStatus") == "Unresolved" for a in authors),
        "SourceCounts": {source: sum(e.get("Source") == source for e in evidence) for source in sorted({e.get("Source") for e in evidence})},
        "Completeness": "not_established",
    }
