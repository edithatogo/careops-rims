"""Extract reconciliable source identities from bounded API/feed payloads."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def validate_source_id_path(path: Any, intake: Any) -> None:
    """Validate structural path syntax and feed-envelope-specific prefixes."""
    if (not isinstance(path, str) or not path or path != path.strip()
            or not isinstance(intake, str) or intake not in {"api", "rss", "atom"}):
        raise ValueError("invalid_source_id_path")
    segments = path.split(".")
    if any(not segment or segment != segment.strip() for segment in segments):
        raise ValueError("invalid_source_id_path")
    names: list[str] = []
    for segment in segments:
        array = segment.endswith("[]")
        name = segment[:-2] if array else segment
        if (not name or "[" in name or "]" in name
                or (not array and ("[" in segment or "]" in segment))):
            raise ValueError("invalid_source_id_path")
        names.append(name.casefold())
    if intake == "atom" and (segments[0].casefold() != "entry[]"):
        raise ValueError("invalid_source_id_path")
    if intake == "rss" and not (
        segments[0].casefold() == "item[]"
        or (len(segments) > 1 and segments[0].casefold() == "channel"
            and segments[1].casefold() == "item[]")
    ):
        raise ValueError("invalid_source_id_path")
    if intake in {"rss", "atom"} and not any(segment.endswith("[]") for segment in segments):
        raise ValueError("invalid_source_id_path")


def json_source_ids(value: Any, path: str) -> list[str]:
    """Read scalar IDs at an explicit dotted JSON path with ``[]`` arrays."""
    validate_source_id_path(path, "api")
    current = [value]
    for segment in path.split("."):
        array = segment.endswith("[]")
        key = segment[:-2] if array else segment
        next_values: list[Any] = []
        for item in current:
            if not isinstance(item, dict) or key not in item:
                raise ValueError("endpoint response has a record without configured reconciliation identity")
            child = item[key]
            if array:
                if not isinstance(child, list):
                    raise ValueError("endpoint response identity collection is not an array")
                next_values.extend(child)
            else:
                next_values.append(child)
        current = next_values
    identifiers: list[str] = []
    for item in current:
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            raise ValueError("endpoint response has a non-scalar reconciliation identity")
        identifier = str(item)
        if not identifier or identifier != identifier.strip():
            raise ValueError("endpoint response has a blank or padded reconciliation identity")
        identifiers.append(identifier)
    return identifiers


def feed_source_ids(payload: str | bytes, path: str, *, intake: str) -> list[str]:
    """Read text IDs at the feed's exact configured structural path."""
    validate_source_id_path(path, intake)
    root = ET.fromstring(payload)
    root_kind = root.tag.rsplit("}", 1)[-1].casefold()
    if root_kind not in ({"rss", "rdf"} if intake == "rss" else {"feed"}):
        raise ValueError("endpoint response has an unsupported feed envelope")
    current = [root]
    for segment in path.split("."):
        array = segment.endswith("[]")
        name = (segment[:-2] if array else segment).casefold()
        following: list[ET.Element] = []
        for node in current:
            matches = [child for child in node
                       if child.tag.rsplit("}", 1)[-1].casefold() == name]
            if not matches and not array:
                raise ValueError("endpoint response has a record without configured reconciliation identity")
            following.extend(matches)
        current = following
    raw_identifiers = [node.text or "" for node in current]
    if any(not identifier for identifier in raw_identifiers):
        raise ValueError("endpoint response has a blank reconciliation identity")
    if any(identifier != identifier.strip() for identifier in raw_identifiers):
        raise ValueError("endpoint response has a padded reconciliation identity")
    identifiers = [" ".join(identifier.split()) for identifier in raw_identifiers]
    return identifiers
