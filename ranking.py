"""Recommendation score: one ordering shared by the site and README.

Weights live in config.SCORE_WEIGHTS so they can be tuned without touching
this file.
"""

from datetime import date, datetime, timedelta, timezone

import config
import filters
from scrapers.base import Posting

_REGION_WEIGHT_KEYS = {
    filters.MILAN: "milan",
    filters.TURIN: "turin",
    filters.ITALY: "italy",
    filters.REMOTE_EUROPE: "remote_europe",
}


def score(p: Posting, today: date | None = None) -> int:
    w = config.SCORE_WEIGHTS
    total = w.get(_REGION_WEIGHT_KEYS.get(filters.region_for_posting(p), ""), 0)
    if p.summer_fit == "yes":
        total += w["summer_fit_yes"]
    elif p.summer_fit == "no":
        total += w["summer_fit_no"]
    if p.summer_program:
        total += w["summer_program"]
    if p.priority == "high":
        total += w["priority_high"]
    if p.role_match:
        total += w["role_match"]
    if filters.is_chem_bio(p.role):
        total += w["chem_bio"]
    if p.degree_req == "phd":
        total += w["degree_phd"]
    elif p.degree_req == "masters":
        total += w["degree_masters"]
    total += _recency_points(effective_date(p), today)
    return round(total)


def effective_date(p: Posting) -> str:
    """The posting's real posted date when known, else when we first saw it."""
    return p.posted_date or p.first_seen or ""


def _recency_points(iso_date: str, today: date | None) -> float:
    try:
        posted = date.fromisoformat(iso_date[:10])
    except ValueError:
        return 0
    today = today or datetime.now(timezone.utc).date()
    age = max((today - posted).days, 0)
    remaining = max(config.RECENCY_DAYS - age, 0) / config.RECENCY_DAYS
    return config.SCORE_WEIGHTS["recency_max"] * remaining


def active(postings, grace_days: int = 3) -> list[Posting]:
    """Postings still listed by their source: last_seen within `grace_days`
    of the newest last_seen overall (a grace window, so one failed scraper
    run doesn't make a company's postings vanish)."""
    postings = list(postings)
    latest = max((p.last_seen for p in postings if p.last_seen), default="")
    if not latest:
        return postings
    cutoff = date.fromisoformat(latest) - timedelta(days=grace_days)
    return [p for p in postings if not p.last_seen or date.fromisoformat(p.last_seen) >= cutoff]


def rank(postings: list[Posting], today: date | None = None) -> list[Posting]:
    """Highest score first, ties broken by newest date."""
    by_date = sorted(postings, key=effective_date, reverse=True)
    return sorted(by_date, key=lambda p: score(p, today), reverse=True)
