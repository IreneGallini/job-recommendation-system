"""Keyword filtering and location normalization for European internship postings."""

import re

import config
from scrapers.base import Posting

# region bucket labels, used to sort the README and Discord messages
MILAN = "milan"
ITALY = "italy"
EUROPE = "europe"
REMOTE_EUROPE = "remote_europe"

_MILAN_ALIASES = {"milan", "milano"}

# UK is deliberately excluded, not just tagged: the user is an EU citizen
# and the UK requires visa sponsorship post-Brexit, unlike the rest of the
# EU/EEA/Switzerland where they have full work authorization.
_UK_MARKERS = (
    "united kingdom", "uk", "great britain", "britain", "england",
    "scotland", "wales", "northern ireland", "gb",
)

# EU + EEA + Switzerland country names/aliases (lowercase) -> canonical country name.
_EUROPE_COUNTRIES = {
    "italy": "Italy", "italia": "Italy",
    "france": "France",
    "germany": "Germany", "deutschland": "Germany",
    "spain": "Spain", "espana": "Spain", "españa": "Spain",
    "portugal": "Portugal",
    "netherlands": "Netherlands", "the netherlands": "Netherlands", "holland": "Netherlands",
    "belgium": "Belgium",
    "luxembourg": "Luxembourg",
    "ireland": "Ireland",
    "austria": "Austria",
    "switzerland": "Switzerland", "svizzera": "Switzerland",
    "poland": "Poland",
    "czech republic": "Czech Republic", "czechia": "Czech Republic",
    "slovakia": "Slovakia",
    "hungary": "Hungary",
    "romania": "Romania",
    "bulgaria": "Bulgaria",
    "greece": "Greece",
    "sweden": "Sweden",
    "denmark": "Denmark",
    "finland": "Finland",
    "norway": "Norway",
    "iceland": "Iceland",
    "lithuania": "Lithuania",
    "latvia": "Latvia",
    "estonia": "Estonia",
    "slovenia": "Slovenia",
    "croatia": "Croatia",
    "serbia": "Serbia",
    "malta": "Malta",
    "cyprus": "Cyprus",
}

_ISO2_TO_COUNTRY = {
    "it": "Italy", "fr": "France", "de": "Germany", "es": "Spain",
    "pt": "Portugal", "nl": "Netherlands", "be": "Belgium", "lu": "Luxembourg",
    "ie": "Ireland", "at": "Austria", "ch": "Switzerland", "pl": "Poland",
    "cz": "Czech Republic", "sk": "Slovakia", "hu": "Hungary", "ro": "Romania",
    "bg": "Bulgaria", "gr": "Greece", "se": "Sweden", "dk": "Denmark",
    "fi": "Finland", "no": "Norway", "is": "Iceland", "lt": "Lithuania",
    "lv": "Latvia", "ee": "Estonia", "si": "Slovenia", "hr": "Croatia",
    "rs": "Serbia", "mt": "Malta", "cy": "Cyprus",
}

_US_MARKERS = ("united states", "usa", "us")
_EXCLUDED_MARKERS = _US_MARKERS + _UK_MARKERS


def _region_for_country(country: str) -> str:
    if country == "Italy":
        return ITALY
    return EUROPE


def normalize_location_text(raw: str) -> tuple[str, str, str] | None:
    """Best-effort parse of a free-text location string.

    Returns (city, country, region) or None if it doesn't look European.
    Handles multi-part strings (comma-joined "City, Country" and
    semicolon-joined multi-location cells) by taking the first European
    match found.
    """
    if not raw:
        return None

    lowered = raw.lower()
    is_remote = bool(re.search(r"\bremote\b", lowered))

    if _contains_word(lowered, _EXCLUDED_MARKERS):
        # An explicit US/UK marker anywhere disqualifies a single-location
        # string, but multi-location cells are handled per-segment below.
        if ";" not in raw and "," not in raw.replace(", ", ";"):
            return None

    for segment in raw.replace(";", ",").split(","):
        seg_lower = segment.strip().lower()
        if not seg_lower:
            continue
        if _contains_word(seg_lower, _EXCLUDED_MARKERS):
            continue
        if seg_lower in _MILAN_ALIASES or _contains_word(seg_lower, ("milan", "milano")):
            return ("Milan", "Italy", MILAN)
        if seg_lower in _EUROPE_COUNTRIES:
            country = _EUROPE_COUNTRIES[seg_lower]
            return ("", country, _region_for_country(country))

    # No explicit country token matched as its own segment; try whole-word
    # matches for "City, Country"-style single segments like "Rome, Italy".
    for country_name, canonical in _EUROPE_COUNTRIES.items():
        if _contains_word(lowered, (country_name,)):
            return ("", canonical, _region_for_country(canonical))

    if is_remote and _contains_word(lowered, ("europe", "emea")):
        return ("", "", REMOTE_EUROPE)

    return None


def _contains_word(text: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in phrases)


def iso2_to_country_name(iso2_country: str) -> str:
    """Best-effort ISO2 -> country display name, for scrapers whose API
    already returns a structured city/country (falls back to the raw code
    uppercased if unrecognized, so it still round-trips through the
    free-text location parser downstream)."""
    return _ISO2_TO_COUNTRY.get((iso2_country or "").strip().lower(), (iso2_country or "").upper())


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text for kw in keywords)


def passes_role_filter(title: str) -> bool:
    lowered = title.lower()
    if _matches_any(lowered, config.EXCLUDE_KEYWORDS):
        return False
    if not _matches_any(lowered, config.INTERN_KEYWORDS):
        return False
    return _matches_any(lowered, config.ROLE_KEYWORDS) or _matches_any(
        lowered, config.CHEM_BIO_KEYWORDS
    )


def filter_and_tag(postings: list[Posting]) -> list[Posting]:
    """Apply role/intern keyword filtering and location normalization.

    Drops non-European and non-matching-role postings; fills in
    country/city/priority region tagging is left to the caller via
    posting.category/priority which scrapers already set. Postings whose
    location can't be resolved to Europe are dropped.
    """
    kept = []
    for p in postings:
        if not passes_role_filter(p.role):
            continue

        result = normalize_location_text(p.location)
        if result is None:
            continue
        city, country, region = result

        p.city = city
        p.country = country
        p.location = _format_location(city, country, region)
        kept.append(p)
    return kept


def _format_location(city: str, country: str, region: str) -> str:
    if region == REMOTE_EUROPE and not country:
        return "Remote (Europe)"
    if city and country:
        return f"{city}, {country}"
    if country:
        return country
    return "Europe"


def region_for_posting(p: Posting) -> str:
    if p.city == "Milan":
        return MILAN
    if p.country == "Italy":
        return ITALY
    if not p.country and "remote" in p.location.lower():
        return REMOTE_EUROPE
    return EUROPE
