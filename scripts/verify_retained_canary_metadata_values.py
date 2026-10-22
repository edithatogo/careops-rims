"""Compare isolated canary bibliography/date fields with captured committed archive files.

Uses the saved summary/chunk bytes, never a fresh PubMed/DoRA request. This
checks selected queryable values only; source uncertainty and full JSON remain
in the ignored archive, and no registry admission follows from a match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCES = {
    "PubMed": ("PubMedPublications", "PubMedMetadataChunks", "PMID", ("Title", "Journal", "Authors", "Abstract", "PublicationDateRaw", "PublicationDatePrecision", "PublicationYear", "OnlineDateRaw")),
    "DORA": ("DoraPublications", "DoraMetadataChunks", "DORAKey", ("Title", "Authors", "Abstract", "PublicationDateRaw", "PublicationDatePrecision", "PublicationYear", "PMID", "DOI", "Journal")),
}
ENGINE_NORMALIZABLE_FIELDS = frozenset({"Title", "Journal", "Authors", "Abstract"})


def _nodes(value):
    # NCBI XML-to-JSON tools may emit either a direct PubmedArticleSet shape
    # or a nested envelope: [{Name: PubmedArticle, Value: [...]}]. Flatten
    # those named wrapper nodes without flattening leaf values/attributes.
    if not isinstance(value, list):
        return []
    flattened = []
    for node in value:
        if (isinstance(node, dict) and node.get("Name") in {"PubmedArticle", "PubmedArticleSet"}
                and isinstance(node.get("Value"), list)):
            flattened.extend(node["Value"])
        else:
            flattened.append(node)
    return flattened


def _children(value, name):
    return [n.get("Value") for n in _nodes(value) if isinstance(n, dict) and n.get("Name") == name]


def _child(value, name):
    return next(iter(_children(value, name)), None)


def _text(value):
    if isinstance(value, list):
        return "".join(_text(n.get("Value")) for n in value if isinstance(n, dict))
    return "" if value is None else str(value)


def _date_raw(value):
    medline = _child(value, "MedlineDate")
    return _text(medline) if medline is not None else " ".join(filter(None, (_text(_child(value, n)) for n in ("Year", "Month", "Day"))))


def _date_parts(raw):
    text = (raw or "").strip()
    parts = [x for x in re.split(r"[ /-]", text) if x]
    year = int(parts[0]) if parts and re.fullmatch(r"\d{4}", parts[0]) else None
    if year is None or not 1500 <= year <= 9999:
        return "unknown", None
    if len(parts) == 1:
        return "year", year
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    month = months.get(parts[1].lower())
    if month is None and parts[1].isdigit():
        month = int(parts[1])
    is_range = "-" in text and not all(x.isdigit() for x in parts)
    if is_range:
        return "range", year
    try:
        import datetime
        day = int(parts[2]) if len(parts) == 3 else 1
        if month is None or len(parts) > 3:
            return "unknown", year
        datetime.date(year, month, day)
    except (ValueError, TypeError):
        return "unknown", year
    return ("day" if len(parts) == 3 else "month"), year


def _pubmed(metadata):
    citation = _child(metadata, "MedlineCitation")
    article = _child(citation, "Article")
    journal = _child(article, "Journal")
    authors = []
    for a in _children(_child(article, "AuthorList"), "Author"):
        collective = _child(a, "CollectiveName")
        if collective is not None:
            name = _text(collective)
        else:
            name = " ".join(filter(None, (_text(_child(a, "ForeName") if _child(a, "ForeName") is not None else _child(a, "Initials")), _text(_child(a, "LastName")), _text(_child(a, "Suffix")))))
        authors.append(name)
    raw = _date_raw(_child(_child(journal, "JournalIssue"), "PubDate"))
    precision, year = _date_parts(raw)
    if year is not None and year < 1900 and precision in ("day", "month"):
        precision = "outside-model-range"
    return {
        "Title": _text(_child(article, "ArticleTitle")),
        "Journal": _text(_child(journal, "Title")),
        "Authors": "; ".join(authors),
        "Abstract": "\n".join(_text(x) for x in _children(_child(article, "Abstract"), "AbstractText")),
        "PublicationDateRaw": raw,
        "PublicationDatePrecision": precision,
        "PublicationYear": year,
    }


def _dora(metadata):
    def values(field):
        return list(dict.fromkeys(x.get("Value") for x in metadata if isinstance(x, dict) and x.get("Field") == field and x.get("Value") is not None))
    def one(field):
        v = values(field)
        if len(v) > 1:
            raise ValueError(f"conflicting single-value DoRA field: {field}")
        return v[0] if v else None
    profile = one("rims.source.format")
    if profile not in (None, "dora_rss_v1"):
        raise ValueError("unsupported retained DoRA metadata profile")
    raw = (one("rims.rss.pubDate") if profile == "dora_rss_v1" else one("dc.date.issued")) or ""
    precision, year = ("unknown", None) if profile == "dora_rss_v1" else _date_parts(raw)
    return {
        "Title": one("dc.title"),
        "Authors": "; ".join(values("dc.contributor.author")),
        "Abstract": "\n".join(values("dc.description.abstract")),
        "PublicationDateRaw": raw,
        "PublicationDatePrecision": precision,
        "PublicationYear": year,
        "PMID": one("dc.identifier.pmid"),
        "DOI": one("dc.identifier.doi"),
        "Journal": one("dc.identifier.journaltitle") if one("dc.identifier.journaltitle") is not None else one("dc.relation.ispartof"),
    }


def _check_dora_identity(identity, summary, metadata, projected):
    url = identity.removeprefix("DORA:")
    if not identity.startswith("DORA:") or summary.get("DORAURL") != url:
        raise ValueError("DoRA summary identity mismatch")
    uris = list(dict.fromkeys(r.get("Value") for r in metadata if isinstance(r, dict) and r.get("Field") == "dc.identifier.uri" and r.get("Value") is not None))
    uri = uris[0] if len(uris) == 1 else None
    if projected["Title"] is None or uri not in (url, url.replace("https://", "http://")):
        raise ValueError("DoRA metadata identity/title mismatch")


def query(source: str, table_override: str | None = None,
          identities: tuple[str, ...] | list[str] | None = None) -> str:
    if source not in SOURCES:
        raise ValueError("unsupported source")
    table = table_override or ("RetainedPubMedPublications" if source == "PubMed" else "RetainedDoraPublications")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", table, flags=re.ASCII):
        raise ValueError("invalid model table name")
    key = SOURCES[source][2]
    columns = (key,) + SOURCES[source][3]
    aliases = ",\n    ".join(f'"{field}", \u0027{table}\u0027[{field}]' for field in columns)
    selected = f"SELECTCOLUMNS('{table}',\n    {aliases})"
    if identities is None:
        return f"EVALUATE\n{selected}"
    if not identities or any(not isinstance(value, str) or not value
                             or any(ch in value for ch in "\x00\r\n") for value in identities):
        raise ValueError("nonempty single-line source identities required for a bounded query")
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate source identities in bounded query")
    literals = ", ".join('\"' + value.replace('\"', '\"\"') + '\"' for value in identities)
    return (f"EVALUATE\nCALCULATETABLE(\n    {selected},\n"
            f"    TREATAS({{{literals}}}, '{table}'[{key}])\n)")


def expected(archive_dir: Path, validated_dir: Path, source: str):
    """Project the already validated complete archive, retaining exact source text."""
    summary_name, _chunk_name, key, fields = SOURCES[source]
    receipt = json.loads((validated_dir / "validated-receipt.json").read_bytes())
    if receipt.get("kind") != "retained_archive_capture_validation_v1":
        raise ValueError("validated archive receipt required")
    batch = receipt["batch_id"]
    if hashlib.sha256((archive_dir / f"commit-{batch}.json").read_bytes()).hexdigest() != receipt["commit_sha256"]:
        raise ValueError("commit manifest hash mismatch")
    spec = receipt["sources"][source]
    metadata_path = validated_dir / f"{source}-metadata.json"
    metadata_bytes = metadata_path.read_bytes()
    if len(metadata_bytes) != spec.get("metadata_map_bytes") or hashlib.sha256(metadata_bytes).hexdigest() != spec.get("metadata_map_sha256"):
        raise ValueError("validated metadata map hash mismatch")
    metadata_map = json.loads(metadata_bytes)
    if len(metadata_map) != spec["metadata_records"]:
        raise ValueError("validated metadata count mismatch")
    summaries = {}
    for index in range(spec["publication_pages"]):
        path = archive_dir / f"uncommitted-{batch}-{summary_name}-{index}.json"
        attested = receipt["files"].get(path.name)
        raw = path.read_bytes()
        if not attested or len(raw) != attested["bytes"] or hashlib.sha256(raw).hexdigest() != attested["sha256"]:
            raise ValueError("summary page hash mismatch")
        for row in json.loads(raw):
            normal = {k.strip("[]"): v for k, v in row.items()}
            identity = normal[key]
            if identity in summaries:
                raise ValueError("duplicate summary identity")
            summaries[identity] = normal
    if len(summaries) != spec["publication_rows"] or set(summaries) != set(metadata_map):
        raise ValueError("validated summary/metadata keyset mismatch")
    output = {}
    for identity, metadata in metadata_map.items():
        projected = _pubmed(metadata) if source == "PubMed" else _dora(metadata)
        if source == "PubMed":
            if _text(_child(_child(metadata, "MedlineCitation"), "PMID")) != identity:
                raise ValueError("PubMed identity mismatch")
            projected["OnlineDateRaw"] = summaries[identity].get("OnlineDateRaw") or ""
        else:
            _check_dora_identity(identity, summaries[identity], metadata, projected)
        output[identity] = {f: projected[f] for f in fields}
    return output


def verify(model_payload: dict, expected_rows: dict, source: str):
    key = SOURCES[source][2]
    fields = SOURCES[source][3]
    result = model_payload["results"]
    if model_payload.get("error") or len(result) != 1 or result[0].get("error") or len(result[0]["tables"]) != 1 or result[0]["tables"][0].get("error"):
        raise ValueError("one successful ExecuteQueries table required")
    rows = result[0]["tables"][0]["rows"]
    aliases = {f"[{f}]" for f in (key,) + fields}
    observed = {}
    differences = []
    normalized = 0
    for row in rows:
        # ExecuteQueries may omit blank properties unless includeNulls is set.
        # A missing property is equivalent to null, never to empty text.
        if not set(row).issubset(aliases) or f"[{key}]" not in row or row[f"[{key}]"] in observed:
            raise ValueError("unexpected aliases or duplicate model identity")
        identity = row[f"[{key}]"]
        observed[identity] = True
        if identity not in expected_rows:
            differences.append({"source_id": identity, "field": "identity", "kind": "unexpected"})
            continue
        for field in fields:
            actual, wanted = row.get(f"[{field}]"), expected_rows[identity][field]
            if actual != wanted:
                if (field in ENGINE_NORMALIZABLE_FIELDS and isinstance(actual, str) and isinstance(wanted, str)
                        and actual.rstrip(" ").casefold() == wanted.rstrip(" ").casefold()):
                    differences.append({"source_id": identity, "field": field, "kind": "engine_text_normalization"})
                    normalized += 1
                else:
                    differences.append({"source_id": identity, "field": field, "kind": "value_mismatch"})
    for identity in expected_rows.keys() - observed.keys():
        differences.append({"source_id": identity, "field": "identity", "kind": "missing"})
    substantive = len(differences) - normalized
    status = "FAIL" if substantive else "PASS_WITH_ENGINE_NORMALIZATION" if normalized else "PASS"
    return {"kind": "retained_canary_metadata_values_v2", "source": source, "status": status,
            "expected_rows": len(expected_rows), "model_rows": len(rows), "differences": len(differences),
            "engine_text_normalizations": normalized, "substantive_differences": substantive,
            "scope": "isolated selected bibliography/raw-date values; source-exact text remains in the validated archive; only display text may vary by Power BI case-insensitive storage and trailing-space trimming; no full JSON, registry, report-bound model or later refresh acceptance"}, differences


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", choices=SOURCES, required=True)
    p.add_argument("--archive-dir", type=Path, required=True)
    p.add_argument("--validated-dir", type=Path, required=True)
    p.add_argument("--print-query", action="store_true")
    p.add_argument("--model", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--differences", type=Path)
    a = p.parse_args()
    if a.print_query:
        print(query(a.source))
        return 0
    if not a.model or not a.output or not a.differences:
        p.error("--model, --output and --differences are required for verification")
    private = (Path(__file__).resolve().parents[1] / "private").resolve()
    if not all(path.resolve().is_relative_to(private) for path in (a.archive_dir, a.validated_dir, a.model, a.output, a.differences)):
        p.error("source, model and detailed outputs must remain under ignored private/")
    if len({p.resolve() for p in (a.model, a.output, a.differences)}) != 3:
        p.error("input and output paths must be distinct")
    expected_rows = expected(a.archive_dir, a.validated_dir, a.source)
    result, differences = verify(json.loads(a.model.read_bytes()), expected_rows, a.source)
    result["inputs"] = {"validated_receipt_sha256": hashlib.sha256((a.validated_dir / "validated-receipt.json").read_bytes()).hexdigest(), "model_sha256": hashlib.sha256(a.model.read_bytes()).hexdigest()}
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    a.differences.write_text(json.dumps(differences, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"PASS", "PASS_WITH_ENGINE_NORMALIZATION"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
