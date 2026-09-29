import csv
import os
from datetime import datetime, timezone
from scrapers.base import Posting

FIELDNAMES = [
    "company", "role", "location", "link", "date_found", "source",
    "country", "city", "category", "priority", "ats", "first_seen",
    "posted_date", "last_seen", "role_match", "summer_program",
    "duration_months", "start_hint", "summer_fit", "degree_req", "described",
]


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def csv_needs_migration(csv_path: str) -> bool:
    """True if the CSV exists but was written with an older header."""
    if not os.path.exists(csv_path):
        return False
    with open(csv_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    return header != FIELDNAMES


def load_all_postings(csv_path: str) -> list[Posting]:
    """Read the full CSV back into Postings. Columns added after a row was
    written (older CSVs) fall back to defaults, so old files load fine."""
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [_row_to_posting(row) for row in csv.DictReader(f)]


def _row_to_posting(row: dict) -> Posting:
    first_seen = row.get("first_seen") or row["date_found"]
    return Posting(
        company=row["company"],
        role=row["role"],
        location=row["location"],
        link=row["link"],
        date_added=row["date_found"],
        source=row["source"],
        country=row.get("country") or "",
        city=row.get("city") or "",
        category=row.get("category") or "unknown",
        priority=row.get("priority") or "normal",
        ats=row.get("ats") or "",
        first_seen=first_seen,
        posted_date=row.get("posted_date") or "",
        last_seen=row.get("last_seen") or first_seen,
        role_match=_parse_bool(row.get("role_match"), default=True),
        summer_program=_parse_bool(row.get("summer_program"), default=False),
        duration_months=row.get("duration_months") or "",
        start_hint=row.get("start_hint") or "",
        summer_fit=row.get("summer_fit") or "unknown",
        degree_req=row.get("degree_req") or "unknown",
        described=_parse_bool(row.get("described"), default=False),
    )


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in ("true", "1", "yes")


def save_all_postings(csv_path: str, postings: list[Posting]) -> None:
    """Rewrite the whole CSV. Called every run (not append-only) so
    `last_seen` stays current and older headers get migrated to the
    current FIELDNAMES."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for p in postings:
            writer.writerow({
                "company": p.company,
                "role": p.role,
                "location": p.location,
                "link": p.link,
                "date_found": p.first_seen or p.date_added,
                "source": p.source,
                "country": p.country,
                "city": p.city,
                "category": p.category,
                "priority": p.priority,
                "ats": p.ats,
                "first_seen": p.first_seen,
                "posted_date": p.posted_date,
                "last_seen": p.last_seen,
                "role_match": str(p.role_match).lower(),
                "summer_program": str(p.summer_program).lower(),
                "duration_months": p.duration_months,
                "start_hint": p.start_hint,
                "summer_fit": p.summer_fit,
                "degree_req": p.degree_req,
                "described": str(p.described).lower(),
            })
