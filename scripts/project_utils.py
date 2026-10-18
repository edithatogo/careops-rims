"""Small deterministic build helpers and testable publication date policy."""
from __future__ import annotations
import calendar
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

def m_text(value: str) -> str:
    """Escape an M text literal. M doubles quotes; it does not use backslashes."""
    return '"' + value.replace('#(', '#(#)(').replace('"', '""').replace('\r', '#(cr)').replace('\n', '#(lf)') + '"'

def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def parse_pub_date(raw: str | None) -> dict[str, Any]:
    """Reference policy mirrored by M; never invent a current year or day 28."""
    text = (raw or '').strip()
    parts = re.split(r'[ /-]+', text) if text else []
    year = int(parts[0]) if parts and re.fullmatch(r'\d{4}', parts[0]) else None
    if year is None or not 1500 <= year <= 9999:
        return {'date': None, 'precision': 'unknown', 'year': None, 'raw': text}
    if len(parts) == 1:
        return {'date': None, 'precision': 'year', 'year': year, 'raw': text}
    # Ranges and seasons retain the original text but do not acquire a false month.
    if '-' in text and not re.fullmatch(r'\d{4}-\d{1,2}(?:-\d{1,2})?', text):
        return {'date': None, 'precision': 'range', 'year': year, 'raw': text}
    months = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
    token = parts[1]
    month = int(token) if token.isdigit() else months.get(token.lower())
    if month is None or not 1 <= month <= 12:
        return {'date': None, 'precision': 'unknown', 'year': year, 'raw': text}
    if len(parts) > 3 or (len(parts) == 3 and not parts[2].isdigit()):
        return {'date': None, 'precision': 'unknown', 'year': year, 'raw': text}
    precision = 'day' if len(parts) == 3 else 'month'
    day = int(parts[2]) if precision == 'day' else 1
    try:
        parsed = date(year, month, day).isoformat()
    except ValueError:
        return {'date': None, 'precision': 'unknown', 'year': year, 'raw': text}
    return {'date': parsed, 'precision': precision, 'year': year, 'raw': text}

def previous_month(at: datetime) -> tuple[date, date]:
    if at.tzinfo is None:
        raise ValueError('Timestamp must be timezone-aware')
    brisbane = at.astimezone(timezone(timedelta(hours=10)))
    end = brisbane.date().replace(day=1)
    start = (end - timedelta(days=1)).replace(day=1)
    return start, end

def set_track(track: str, evidence: list[str], review: str) -> None:
    folder = ROOT / 'conductor/tracks' / track
    plan = folder / 'plan.md'
    plan.write_text(plan.read_text().replace('[ ]', '[x]'))
    meta = json.loads((folder / 'metadata.json').read_text())
    meta.update(status='completed', evidence=evidence, reviewed='2026-09-11')
    save_json(folder / 'metadata.json', meta)
    (folder / 'review.md').write_text('# Review\n\n' + review + '\n')
    index = ROOT / 'conductor/tracks.md'
    index.write_text(index.read_text().replace(f'- [ ] [{track}', f'- [x] [{track}'))
