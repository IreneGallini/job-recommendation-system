"""Parse duration, start timing, summer fit and degree requirements out of a
posting's title + description (English and Italian, plus a few German /
French / Spanish terms).

The user is available mid-May to early September (~14-16 weeks), so fixed
6-month internships usually won't work — `summer_fit` captures that.
"""

import html
import re
from datetime import date

from scrapers.base import Posting

_TAG_RE = re.compile(r"<[^>]+>")

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "un": 1, "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6,
    "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12,
}
_NUM = r"(\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")"
_MONTH_UNITS = r"(?:months?|mesi|mese|monate?n?|mois|meses?)"
_WEEK_UNITS = r"(?:weeks?|settimane|settimana|wochen|woche|semaines?|semanas?)"
# "3 months", "3-6 months", "6-month", "sei mesi", "durata: 6 mesi"
_DURATION_RE = re.compile(
    rf"\b{_NUM}(?:\s*(?:-|–|to|a|bis)\s*{_NUM})?\s*-?\s*({_MONTH_UNITS}|{_WEEK_UNITS})\b",
    re.IGNORECASE,
)
# Durations that describe required experience, not the internship itself.
_EXPERIENCE_AFTER_RE = re.compile(
    r"^\W{0,3}(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?(?:experience|esperienza|erfahrung)",
    re.IGNORECASE,
)

_MONTHS = {
    "january": 1, "jan": 1, "gennaio": 1, "januar": 1, "janvier": 1, "enero": 1,
    "february": 2, "feb": 2, "febbraio": 2, "februar": 2, "février": 2, "febrero": 2,
    "march": 3, "mar": 3, "marzo": 3, "märz": 3, "mars": 3,
    "april": 4, "apr": 4, "aprile": 4, "avril": 4, "abril": 4,
    "may": 5, "maggio": 5, "mai": 5, "mayo": 5,
    "june": 6, "jun": 6, "giugno": 6, "juni": 6, "juin": 6, "junio": 6,
    "july": 7, "jul": 7, "luglio": 7, "juli": 7, "juillet": 7, "julio": 7,
    "august": 8, "aug": 8, "agosto": 8, "août": 8,
    "september": 9, "sep": 9, "sept": 9, "settembre": 9, "septembre": 9, "septiembre": 9,
    "october": 10, "oct": 10, "ottobre": 10, "oktober": 10, "octobre": 10, "octubre": 10,
    "november": 11, "nov": 11, "novembre": 11, "noviembre": 11,
    "december": 12, "dec": 12, "dicembre": 12, "dezember": 12, "décembre": 12, "diciembre": 12,
}
_MONTH_ABBREV = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}
_MONTH_NAMES = r"(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")"
_START_RE = re.compile(
    r"\b(?:start(?:ing)?(?:\s+date)?|begin(?:ning|s)?|inizio|data di inizio|"
    r"a partire da|beginn|ab|début|à partir de|from|dal|da|comienzo|"
    r"fecha de (?:ingreso|inicio|incorporación)|incorporación)\b"
    rf"\W{{0,3}}(?:in\s+|di\s+|im\s+|en\s+|early\s+|mid[-\s]|late\s+|inizio\s+|metà\s+)?{_MONTH_NAMES}\b"
    # "start date may vary" is the modal verb, not the month
    r"(?!\s+(?:be|vary|change|differ|also|depend|require|include))",
    re.IGNORECASE,
)
_SUMMER_RE = re.compile(
    r"\bsummer\s+(?:intern|internship|internships|program|programme|analyst|student|20\d\d)\b|"
    r"\bstage\s+estivo\b|\btirocinio\s+estivo\b|\bsommerpraktikum\b|"
    r"\bstage\s+d['’]été\b|\bprácticas\s+de\s+verano\b|\bestate\s+20\d\d\b",
    re.IGNORECASE,
)
_ASAP_RE = re.compile(
    r"\b(?:asap|as soon as possible|immediately|immediate start|il prima possibile|"
    r"da subito|inizio immediato|ab sofort|dès que possible)\b",
    re.IGNORECASE,
)

_BACHELOR_RE = re.compile(
    r"\bbachelor|\bundergraduate|\blaurea triennale|\bb\.?sc\b|\bb\.s\.|\bbachelorstudium",
    re.IGNORECASE,
)
_MASTER_RE = re.compile(
    r"\bmaster['’]?s\b|\bmaster\s+(?:degree|student|program|programme|of science)|"
    r"\bm\.?sc\b|\blaurea magistrale\b|\bmasterstudi",
    re.IGNORECASE,
)
_PHD_RE = re.compile(r"\bph\.?\s?d\b|\bdoctora(?:l|te)\b|\bdottorato\b|\bdoktorand", re.IGNORECASE)


def strip_html(text: str) -> str:
    # Personio wraps descriptions in CDATA; drop the markers first or the
    # tag regex would swallow the whole section as one "tag". Greenhouse
    # HTML arrives entity-escaped, hence the double unescape.
    text = (text or "").replace("<![CDATA[", " ").replace("]]>", " ")
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html.unescape(html.unescape(text)))).strip()


def parse_duration(text: str) -> float | None:
    """Months of internship duration, or None if not stated. For a range
    ("3-6 months") the lower bound is used — a flexible range may still fit
    the summer."""
    for match in _DURATION_RE.finditer(text):
        if _EXPERIENCE_AFTER_RE.match(text[match.end():match.end() + 40]):
            continue
        low = _to_number(match.group(1))
        unit = match.group(3).lower()
        if low is None:
            continue
        if re.match(_WEEK_UNITS, unit, re.IGNORECASE):
            return round(low / 4.33, 1)
        return float(low)
    return None


def _to_number(token: str | None) -> int | None:
    if token is None:
        return None
    token = token.lower()
    return int(token) if token.isdigit() else _NUMBER_WORDS.get(token)


def parse_start_hint(text: str, reference: date | None = None) -> str:
    """"summer" for an explicit summer program, a month abbreviation
    ("sep") for a stated start month, or "" if nothing is stated. "ASAP"
    resolves to the reference month (when the posting was first seen)."""
    if _SUMMER_RE.search(text):
        return "summer"
    match = _START_RE.search(text)
    if match:
        return _MONTH_ABBREV[_MONTHS[match.group(1).lower()]]
    if _ASAP_RE.search(text) and reference is not None:
        return _MONTH_ABBREV[reference.month]
    return ""


def summer_fit(duration_months: float | None, start_hint: str) -> str:
    """yes: explicit summer program, or <= 4 months starting May-June.
    no: clearly >= 5 months, or starts September-March.
    unknown: everything else (never dropped, just sorted after "yes")."""
    start_month = next((n for n, name in _MONTH_ABBREV.items() if name == start_hint), None)
    if duration_months is not None and duration_months >= 5:
        return "no"
    if start_hint == "summer":
        return "yes"
    if start_month is not None and (start_month >= 9 or start_month <= 3):
        return "no"
    if duration_months is not None and duration_months <= 4 and start_month in (5, 6):
        return "yes"
    return "unknown"


def degree_req(text: str) -> str:
    """phd: only a PhD is mentioned. masters: a Master's (or Master's/PhD)
    is required and a Bachelor's isn't accepted. any: a Bachelor's is
    accepted. unknown: no degree level mentioned."""
    if _BACHELOR_RE.search(text):
        return "any"
    has_master = bool(_MASTER_RE.search(text))
    if _PHD_RE.search(text) and not has_master:
        return "phd"
    if has_master:
        return "masters"
    return "unknown"


def enrich(posting: Posting) -> None:
    text = f"{posting.role}\n{strip_html(posting.description)}"
    reference = _parse_iso(posting.posted_date) or _parse_iso(posting.first_seen)
    duration = parse_duration(text)
    start = parse_start_hint(text, reference)
    posting.duration_months = _format_months(duration)
    posting.start_hint = start
    posting.summer_fit = summer_fit(duration, start)
    posting.degree_req = degree_req(text)


def _format_months(months: float | None) -> str:
    if months is None:
        return ""
    return str(int(months)) if months == int(months) else str(months)


def _parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None
