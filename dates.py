"""Normalize each source's posted-date format to an ISO date (YYYY-MM-DD)."""

import re
from datetime import date, datetime, timedelta, timezone

_WORKDAY_DAYS_AGO_RE = re.compile(r"(\d+)\+?\s+days?\s+ago", re.IGNORECASE)


def normalize_posted_date(raw, today: date | None = None) -> str:
    """Best-effort parse; returns "" if the value can't be understood.

    Handles ISO-8601 strings (Greenhouse, Ashby, SmartRecruiters, Workable,
    Teamtailor, Personio), epoch-millisecond timestamps (Lever), and
    Workday's relative "Posted Today" / "Posted Yesterday" /
    "Posted 3 Days Ago" / "Posted 30+ Days Ago" text. "30+ Days Ago" is
    only a lower bound, so it resolves to 30 days back.
    """
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    today = today or datetime.now(timezone.utc).date()

    if text.isdigit() and len(text) >= 12:
        return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc).date().isoformat()

    lowered = text.lower()
    if "today" in lowered or "just posted" in lowered:
        return today.isoformat()
    if "yesterday" in lowered:
        return (today - timedelta(days=1)).isoformat()
    match = _WORKDAY_DAYS_AGO_RE.search(lowered)
    if match:
        return (today - timedelta(days=int(match.group(1)))).isoformat()

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else ""
