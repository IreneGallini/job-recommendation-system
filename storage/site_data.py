"""Write the JSON data files the GitHub Pages site (docs/) renders.

docs/index.html, app.js and style.css are hand-written and committed; only
postings.json and outreach.json are regenerated here, every run.
"""

import json
import os
import re
from datetime import datetime, timezone

import yaml

import filters
import ranking
from scrapers.base import Posting


def write_site_data(docs_dir: str, postings: list[Posting], outreach_yaml_path: str) -> None:
    os.makedirs(docs_dir, exist_ok=True)
    active_links = {p.link for p in ranking.active(postings)}
    ranked = ranking.rank(postings)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="minutes")

    _write_json(os.path.join(docs_dir, "postings.json"), {
        "generated_at": generated_at,
        "postings": [_posting_json(p, p.link in active_links) for p in ranked],
    })
    _write_json(os.path.join(docs_dir, "outreach.json"), {
        "generated_at": generated_at,
        "contacts": _outreach_json(outreach_yaml_path, [p for p in ranked if p.link in active_links]),
    })


def _posting_json(p: Posting, active: bool) -> dict:
    return {
        "link": p.link,
        "company": p.company,
        "role": p.role,
        "location": p.location,
        "city": p.city,
        "country": p.country,
        "region": filters.region_for_posting(p),
        "category": p.category,
        "priority": p.priority,
        "source": p.source,
        "posted_date": p.posted_date,
        "first_seen": p.first_seen,
        "last_seen": p.last_seen,
        "active": active,
        "role_match": p.role_match,
        "chem_bio": filters.is_chem_bio(p.role),
        "summer_program": p.summer_program,
        "summer_fit": p.summer_fit,
        "duration_months": p.duration_months,
        "start_hint": p.start_hint,
        "degree_req": p.degree_req,
        "score": ranking.score(p),
    }


def _outreach_json(path: str, active_ranked: list[Posting]) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []

    contacts = []
    for entry in entries:
        company = entry.get("company", "")
        matching = [p for p in active_ranked if p.company.lower() == company.lower()]
        contacts.append({
            "id": entry.get("id") or _slug(f"{company}-{entry.get('contact_role', '')}"),
            "company": company,
            "why": entry.get("why", ""),
            "contact_role": entry.get("contact_role", ""),
            "name": entry.get("name", ""),
            "link": entry.get("link", ""),
            "careers_url": entry.get("careers_url", ""),
            "notes": entry.get("notes", ""),
            "priority": entry.get("priority", "normal"),
            "open_postings": [
                {"role": p.role, "link": p.link, "role_match": p.role_match}
                for p in matching[:5]
            ],
            "open_postings_total": len(matching),
        })
    return contacts


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
