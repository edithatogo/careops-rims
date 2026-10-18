"""Parse bounded, review-only grant calendar HTML tables.

This adapter is deliberately not an unattended importer.  It extracts rows
from an explicitly selected table shape, preserves raw date text, and emits
candidate records for the reviewed-import gate.  It does not infer a URL for a
row, eligibility, or an exact deadline when the source only supplies a
partial/range value.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.row_links: list[list[str]] = []
        self._row: list[str] | None = None
        self._row_links: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
            self._row_links = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "a" and self._cell is not None and self._row_links is not None:
            href = dict(attrs).get("href")
            if href:
                self._row_links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
                self.row_links.append(self._row_links or [])
            self._row = None
            self._row_links = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_calendar_html(
    html: str | bytes,
    *,
    source: str,
    source_url: str,
    retrieved_utc: str,
    required_headers: Iterable[str] = ("title", "close"),
) -> dict[str, Any]:
    """Return candidate rows from the first table containing required headers."""
    parsed_source_url = urlsplit(source_url) if isinstance(source_url, str) else None
    if (
        not isinstance(source, str)
        or not source.strip()
        or source != source.strip()
        or not isinstance(source_url, str)
        or source_url != source_url.strip()
        or parsed_source_url is None
        or parsed_source_url.scheme != "https"
        or not parsed_source_url.netloc
    ):
        raise ValueError("source and HTTPS source_url are required")
    if not retrieved_utc.endswith(("Z", "+00:00")):
        raise ValueError("retrieved_utc must include an explicit UTC offset")
    body = html.decode("utf-8", "replace") if isinstance(html, bytes) else html
    parser = _TableParser()
    parser.feed(body)
    selected: list[list[str]] | None = None
    headers: list[str] = []
    requested = {item.casefold() for item in required_headers}
    for index, row in enumerate(parser.rows):
        normalized = [cell.casefold() for cell in row]
        has_title = any(item in normalized for item in ("title", "funding scheme", "grant opportunity"))
        has_close = any(item in normalized for item in ("close", "applications close"))
        if ("title" not in requested or has_title) and ("close" not in requested or has_close):
            selected = parser.rows[index:]
            headers = normalized
            break
    if selected is None:
        return {
            "status": "no_matching_table",
            "source": source,
            "source_url": source_url,
            "retrieved_utc": retrieved_utc,
            "records": [],
        }
    positions = {header: headers.index(header) for header in headers}
    records: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    selected_links = parser.row_links[index:]
    for row_index, row in enumerate(selected[1:], start=1):
        if len(row) < len(headers) or not any(row):
            continue
        if [cell.casefold() for cell in row] == headers:
            continue
        title_index = positions.get("title", positions.get("funding scheme", positions.get("grant opportunity")))
        close_index = positions.get("close", positions.get("applications close"))
        if title_index is None or close_index is None:
            continue
        title = row[title_index].strip()
        deadline_raw = row[close_index].strip()
        if not title:
            continue
        source_id = hashlib.sha256(
            f"{source}|{json.dumps(row, ensure_ascii=False, separators=(',', ':'))}".encode("utf-8")
        ).hexdigest()[:24]
        if source_id in seen_source_ids:
            return {
                "status": "duplicate_source_identity",
                "source": source,
                "source_url": source_url,
                "retrieved_utc": retrieved_utc,
                "table_headers": headers,
                "records": [],
            }
        seen_source_ids.add(source_id)
        row_links = selected_links[row_index] if row_index < len(selected_links) else []
        actionable_links = [
            link for link in row_links
            if isinstance(link, str)
            and link == link.strip()
            and urlsplit(link).scheme in {"http", "https"}
            and bool(urlsplit(link).netloc)
        ]
        records.append({
            "Source": source,
            "SourceID": source_id,
            "Title": title,
            "URL": source_url,
            # Row links are evidence candidates only; a missing or ambiguous
            # link remains explicit instead of being inferred from the title.
            "SourceLinks": actionable_links,
            "SourceRowURL": actionable_links[0] if len(actionable_links) == 1 else "",
            # Preserve the complete observed table row so reviewers retain
            # source context beyond the normalised title and date fields.
            "SourceColumns": dict(zip(headers, row)),
            # Keep positional cells too: duplicate source headers must not
            # cause evidence loss through dictionary key collision.
            "SourceCells": [
                {"header": header, "value": value}
                for header, value in zip(headers, row)
            ],
            "Deadline": None,
            "DeadlineRaw": deadline_raw,
            "Status": "Needs Review",
            "ReviewStatus": "Needs Review",
            "ReviewNotes": "Extracted from an official HTML calendar; review row link, status, eligibility and date precision before import.",
            "RetrievedUTC": retrieved_utc,
        })
    return {
        "status": "candidate_rows",
        "source": source,
        "source_url": source_url,
        "retrieved_utc": retrieved_utc,
        "table_headers": headers,
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    retrieved = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = parse_calendar_html(args.html.read_bytes(), source=args.source, source_url=args.source_url, retrieved_utc=retrieved)
    payload = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
