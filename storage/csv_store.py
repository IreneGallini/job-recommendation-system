import csv
import os
from datetime import datetime, timezone
from scrapers.base import Posting

FIELDNAMES = [
    "company", "role", "location", "link", "date_found", "source",
    "country", "city", "category", "priority", "ats", "first_seen",
]


def load_seen_links(csv_path: str) -> set[str]:
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        return {row["link"] for row in csv.DictReader(f) if row.get("link")}


def load_all_postings(csv_path: str) -> list[Posting]:
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [
            Posting(
                company=row["company"],
                role=row["role"],
                location=row["location"],
                link=row["link"],
                date_added=row["date_found"],
                source=row["source"],
                country=row.get("country", ""),
                city=row.get("city", ""),
                category=row.get("category", "unknown"),
                priority=row.get("priority", "normal"),
                ats=row.get("ats", ""),
                first_seen=row.get("first_seen", row["date_found"]),
            )
            for row in csv.DictReader(f)
        ]


def append_new_postings(csv_path: str, postings: list[Posting]) -> None:
    if not postings:
        return
    write_header = not os.path.exists(csv_path)
    date_found = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        for p in postings:
            writer.writerow({
                "company": p.company,
                "role": p.role,
                "location": p.location,
                "link": p.link,
                "date_found": date_found,
                "source": p.source,
                "country": p.country,
                "city": p.city,
                "category": p.category,
                "priority": p.priority,
                "ats": p.ats,
                "first_seen": p.first_seen or date_found,
            })
