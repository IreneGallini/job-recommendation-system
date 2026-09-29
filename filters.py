"""Keyword filtering and location normalization for European internship postings."""

import re

import config
import dates
from scrapers.base import Posting

# region bucket labels, used to sort the README and Discord messages
MILAN = "milan"
TURIN = "turin"
ITALY = "italy"
EUROPE = "europe"
REMOTE_EUROPE = "remote_europe"

# Region preference order, best first; used to pick the best location out of
# a multi-location posting.
_REGION_RANK = {MILAN: 0, TURIN: 1, ITALY: 2, EUROPE: 3, REMOTE_EUROPE: 4}

# UK is deliberately excluded, not just tagged: the user is an EU citizen
# and the UK requires visa sponsorship post-Brexit, unlike the rest of the
# EU/EEA/Switzerland where they have full work authorization.
_UK_MARKERS = (
    "united kingdom", "uk", "great britain", "britain", "england",
    "scotland", "wales", "northern ireland", "gb",
)

# Eligible countries only (lowercase names/aliases, incl. native spellings)
# -> canonical country name. This is a deliberate allowlist, not the full
# EU/EEA: any country not listed here is dropped.
_EUROPE_COUNTRIES = {
    "italy": "Italy", "italia": "Italy",
    "switzerland": "Switzerland", "svizzera": "Switzerland",
    "schweiz": "Switzerland", "suisse": "Switzerland",
    "france": "France",
    "germany": "Germany", "deutschland": "Germany",
    "denmark": "Denmark", "danmark": "Denmark",
    "norway": "Norway", "norge": "Norway",
    "sweden": "Sweden", "sverige": "Sweden",
    "finland": "Finland", "suomi": "Finland",
    "spain": "Spain", "espana": "Spain", "españa": "Spain",
    "portugal": "Portugal",
    "netherlands": "Netherlands", "the netherlands": "Netherlands",
    "holland": "Netherlands", "nederland": "Netherlands",
    "belgium": "Belgium", "belgië": "Belgium", "belgique": "Belgium",
    "austria": "Austria", "österreich": "Austria", "osterreich": "Austria",
    "ireland": "Ireland",
}

_ISO2_TO_COUNTRY = {
    "it": "Italy", "ch": "Switzerland", "fr": "France", "de": "Germany",
    "dk": "Denmark", "no": "Norway", "se": "Sweden", "fi": "Finland",
    "es": "Spain", "pt": "Portugal", "nl": "Netherlands", "be": "Belgium",
    "at": "Austria", "ie": "Ireland",
}

# Well-known cities in the eligible countries (lowercase alias -> (display
# name, country)), so city-only location strings like "Milano" or "Zürich"
# resolve. Milan/Turin-area suburbs are listed in config.MILAN_AREA_CITIES /
# config.TURIN_AREA_CITIES and added below.
_CITIES = {
    # Italy
    "milan": ("Milan", "Italy"), "milano": ("Milan", "Italy"),
    "turin": ("Turin", "Italy"), "torino": ("Turin", "Italy"),
    "rome": ("Rome", "Italy"), "roma": ("Rome", "Italy"),
    "naples": ("Naples", "Italy"), "napoli": ("Naples", "Italy"),
    "florence": ("Florence", "Italy"), "firenze": ("Florence", "Italy"),
    "genoa": ("Genoa", "Italy"), "genova": ("Genoa", "Italy"),
    "venice": ("Venice", "Italy"), "venezia": ("Venice", "Italy"),
    "padua": ("Padua", "Italy"), "padova": ("Padua", "Italy"),
    "bologna": ("Bologna", "Italy"), "verona": ("Verona", "Italy"),
    "trento": ("Trento", "Italy"), "pisa": ("Pisa", "Italy"),
    "parma": ("Parma", "Italy"), "bergamo": ("Bergamo", "Italy"),
    "brescia": ("Brescia", "Italy"), "bari": ("Bari", "Italy"),
    "catania": ("Catania", "Italy"), "modena": ("Modena", "Italy"),
    # Switzerland
    "zurich": ("Zurich", "Switzerland"), "zürich": ("Zurich", "Switzerland"),
    "geneva": ("Geneva", "Switzerland"), "genève": ("Geneva", "Switzerland"),
    "geneve": ("Geneva", "Switzerland"), "basel": ("Basel", "Switzerland"),
    "lausanne": ("Lausanne", "Switzerland"), "bern": ("Bern", "Switzerland"),
    "lugano": ("Lugano", "Switzerland"), "zug": ("Zug", "Switzerland"),
    # France
    "paris": ("Paris", "France"), "lyon": ("Lyon", "France"),
    "toulouse": ("Toulouse", "France"), "grenoble": ("Grenoble", "France"),
    "sophia antipolis": ("Sophia Antipolis", "France"), "nice": ("Nice", "France"),
    "marseille": ("Marseille", "France"), "lille": ("Lille", "France"),
    "bordeaux": ("Bordeaux", "France"), "nantes": ("Nantes", "France"),
    # Germany
    "munich": ("Munich", "Germany"), "münchen": ("Munich", "Germany"),
    "muenchen": ("Munich", "Germany"), "berlin": ("Berlin", "Germany"),
    "hamburg": ("Hamburg", "Germany"), "frankfurt": ("Frankfurt", "Germany"),
    "stuttgart": ("Stuttgart", "Germany"), "cologne": ("Cologne", "Germany"),
    "köln": ("Cologne", "Germany"), "düsseldorf": ("Düsseldorf", "Germany"),
    "dusseldorf": ("Düsseldorf", "Germany"), "heidelberg": ("Heidelberg", "Germany"),
    "karlsruhe": ("Karlsruhe", "Germany"), "erlangen": ("Erlangen", "Germany"),
    "nuremberg": ("Nuremberg", "Germany"), "nürnberg": ("Nuremberg", "Germany"),
    "darmstadt": ("Darmstadt", "Germany"), "dresden": ("Dresden", "Germany"),
    "leipzig": ("Leipzig", "Germany"), "aachen": ("Aachen", "Germany"),
    # Netherlands
    "amsterdam": ("Amsterdam", "Netherlands"), "eindhoven": ("Eindhoven", "Netherlands"),
    "rotterdam": ("Rotterdam", "Netherlands"), "utrecht": ("Utrecht", "Netherlands"),
    "the hague": ("The Hague", "Netherlands"), "delft": ("Delft", "Netherlands"),
    "leiden": ("Leiden", "Netherlands"),
    # Belgium
    "brussels": ("Brussels", "Belgium"), "bruxelles": ("Brussels", "Belgium"),
    "antwerp": ("Antwerp", "Belgium"), "ghent": ("Ghent", "Belgium"),
    "leuven": ("Leuven", "Belgium"),
    # Austria
    "vienna": ("Vienna", "Austria"), "wien": ("Vienna", "Austria"),
    "graz": ("Graz", "Austria"), "linz": ("Linz", "Austria"),
    "salzburg": ("Salzburg", "Austria"), "innsbruck": ("Innsbruck", "Austria"),
    # Ireland
    "dublin": ("Dublin", "Ireland"), "cork": ("Cork", "Ireland"),
    "galway": ("Galway", "Ireland"), "limerick": ("Limerick", "Ireland"),
    # Spain
    "madrid": ("Madrid", "Spain"), "barcelona": ("Barcelona", "Spain"),
    "valencia": ("Valencia", "Spain"), "seville": ("Seville", "Spain"),
    "sevilla": ("Seville", "Spain"), "malaga": ("Málaga", "Spain"),
    "málaga": ("Málaga", "Spain"), "bilbao": ("Bilbao", "Spain"),
    # Portugal
    "lisbon": ("Lisbon", "Portugal"), "lisboa": ("Lisbon", "Portugal"),
    "porto": ("Porto", "Portugal"), "braga": ("Braga", "Portugal"),
    "aveiro": ("Aveiro", "Portugal"), "coimbra": ("Coimbra", "Portugal"),
    # Nordics
    "copenhagen": ("Copenhagen", "Denmark"), "københavn": ("Copenhagen", "Denmark"),
    "aarhus": ("Aarhus", "Denmark"), "odense": ("Odense", "Denmark"),
    "oslo": ("Oslo", "Norway"), "bergen": ("Bergen", "Norway"),
    "trondheim": ("Trondheim", "Norway"), "stavanger": ("Stavanger", "Norway"),
    "stockholm": ("Stockholm", "Sweden"), "gothenburg": ("Gothenburg", "Sweden"),
    "göteborg": ("Gothenburg", "Sweden"), "malmö": ("Malmö", "Sweden"),
    "malmo": ("Malmö", "Sweden"), "lund": ("Lund", "Sweden"),
    "uppsala": ("Uppsala", "Sweden"), "helsinki": ("Helsinki", "Finland"),
    "espoo": ("Espoo", "Finland"), "tampere": ("Tampere", "Finland"),
    "oulu": ("Oulu", "Finland"), "turku": ("Turku", "Finland"),
}
for _alias in config.MILAN_AREA_CITIES:
    _CITIES.setdefault(_alias, (_alias.title(), "Italy"))
for _alias in config.TURIN_AREA_CITIES:
    _CITIES.setdefault(_alias, (_alias.title(), "Italy"))

_US_MARKERS = ("united states", "usa", "us")
_EXCLUDED_MARKERS = _US_MARKERS + _UK_MARKERS

# Many European city names also exist in the US (Dublin OH/CA, Vienna VA,
# Paris TX, Naples FL, Milan TN...). A bare city match is rejected if the
# same location also names a US state; an explicit European country name
# still wins (so "Munich, Germany" is fine).
_US_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV "
    "WI WY DC".split()
)
_US_STATE_NAMES = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
)


def region_for(city: str, country: str, remote: bool = False) -> str:
    city_lower = city.lower()
    if city_lower in config.MILAN_AREA_CITIES or city_lower in ("milan", "milano"):
        return MILAN
    if city_lower in config.TURIN_AREA_CITIES or city_lower in ("turin", "torino"):
        return TURIN
    if country == "Italy":
        return ITALY
    if not country and remote:
        return REMOTE_EUROPE
    return EUROPE


def normalize_location_text(raw: str) -> tuple[str, str, str] | None:
    """Best-effort parse of a free-text location string.

    Returns (city, country, region) or None if it doesn't resolve to an
    eligible country. Multi-location cells (joined with ";" or "|") are
    parsed one location at a time and the most preferred one wins
    (Milan > Turin > rest of Italy > rest of Europe > remote-Europe).
    Within one location, comma-separated parts are scanned for a country
    and a city in any order ("Munich, Germany" and Workday's
    "Germany, Munich" both work).
    """
    if not raw:
        return None

    candidates = []
    for location in re.split(r"[;|]", raw):
        result = _parse_single_location(location)
        if result is not None:
            candidates.append(result)

    if not candidates:
        return None
    return min(candidates, key=lambda c: _REGION_RANK[c[2]])


def _parse_single_location(location: str) -> tuple[str, str, str] | None:
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if not parts:
        return None
    lowered = location.lower()
    # An explicit US/UK marker disqualifies the whole location (so
    # "Belfast, Northern Ireland" can't whole-word-match "ireland").
    if _contains_word(lowered, _EXCLUDED_MARKERS):
        return None

    names_us_state = any(p in _US_STATE_CODES for p in parts) or _contains_word(
        lowered, _US_STATE_NAMES
    )

    country = ""
    country_part = None
    for part in parts:
        country = _match_country(part.lower())
        if country:
            country_part = part
            break

    city = ""
    for part in parts:
        match = _match_city(part.lower())
        if match and (not country or match[1] == country):
            city, city_country = match
            country = country or city_country
            break

    if not country:
        if city or names_us_state:
            return None
        if re.search(r"\bremote\b", lowered) and _contains_word(lowered, ("europe", "emea")):
            return ("", "", REMOTE_EUROPE)
        return None
    if names_us_state and country_part is None:
        return None

    if not city:
        # Unknown city next to a known country ("Segrate, Italy"): keep the
        # other part as the city name if it looks like one.
        others = [
            p for p in parts
            if p is not country_part and not re.search(r"\d|remote|hybrid|office", p, re.IGNORECASE)
        ]
        if others and len(others[0]) <= 40:
            city = others[0]

    return (city, country, region_for(city, country))


def _match_country(text: str) -> str:
    match = _COUNTRY_RE.search(text)
    return _EUROPE_COUNTRIES[match.group(0)] if match else ""


def _match_city(text: str) -> tuple[str, str] | None:
    match = _CITY_RE.search(text)
    return _CITIES[match.group(0)] if match else None


def _word_regex(phrases) -> re.Pattern:
    """One precompiled whole-word alternation (longest phrase first, so
    "the netherlands" wins over "netherlands"). Building a fresh pattern per
    phrase per call overflowed re's 512-entry cache with several hundred
    city/country/state names and made parsing ~12k locations take minutes."""
    alternatives = "|".join(re.escape(p) for p in sorted(set(phrases), key=len, reverse=True))
    return re.compile(rf"\b(?:{alternatives})\b")


_word_regex_cache: dict[tuple[str, ...], re.Pattern] = {}


def _contains_word(text: str, phrases: tuple[str, ...]) -> bool:
    pattern = _word_regex_cache.get(phrases)
    if pattern is None:
        pattern = _word_regex_cache[phrases] = _word_regex(phrases)
    return bool(pattern.search(text))


_COUNTRY_RE = _word_regex(_EUROPE_COUNTRIES)
_CITY_RE = _word_regex(_CITIES)


def iso2_to_country_name(iso2_country: str) -> str:
    """Best-effort ISO2 -> country display name, for scrapers whose API
    already returns a structured city/country (falls back to the raw code
    uppercased if unrecognized, so it still round-trips through the
    free-text location parser downstream)."""
    return _ISO2_TO_COUNTRY.get((iso2_country or "").strip().lower(), (iso2_country or "").upper())


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text for kw in keywords)


# "intern" and "stage" must be whole words ("International", "Internal",
# "backstage", "multi-stage" are not internships); the rest are matched as
# substrings so German compounds like "Pflichtpraktikum" still hit.
_WHOLE_WORD_INTERN_KEYWORDS = ("intern", "stage")
_INTERN_RE = re.compile(
    "|".join(
        # (?<![\w-]) rather than \b so hyphenated compounds ("multi-stage")
        # don't count as the standalone word.
        rf"(?<![\w-]){re.escape(kw)}s?(?![\w-])" if kw in _WHOLE_WORD_INTERN_KEYWORDS else re.escape(kw)
        for kw in config.INTERN_KEYWORDS
    )
)


def is_internship(title: str) -> bool:
    lowered = title.lower()
    if _matches_any(lowered, config.EXCLUDE_KEYWORDS):
        return False
    return bool(_INTERN_RE.search(lowered))


def matches_target_role(title: str) -> bool:
    lowered = title.lower()
    return _matches_any(lowered, config.ROLE_KEYWORDS) or is_chem_bio(title)


def is_chem_bio(title: str) -> bool:
    return _matches_any(title.lower(), config.CHEM_BIO_KEYWORDS)


def filter_and_tag(postings: list[Posting]) -> list[Posting]:
    """Keep every internship in an eligible country; tag the rest.

    Drops non-internships and anything whose location doesn't resolve to an
    eligible country or remote-Europe. Postings outside the target roles are
    kept (for the site's "All" tab) but tagged `role_match=False`; the
    README, Discord and the site's Inbox only show `role_match=True`.
    Also normalizes location to (city, country) and the ATS's raw date to
    `posted_date`.
    """
    kept = []
    for p in postings:
        if not is_internship(p.role):
            continue

        result = normalize_location_text(p.location)
        if result is None:
            continue
        city, country, region = result

        p.city = city
        p.country = country
        p.location = _format_location(city, country, region)
        p.role_match = matches_target_role(p.role)
        p.posted_date = p.posted_date or dates.normalize_posted_date(p.date_added)
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
    return region_for(p.city, p.country, remote="remote" in p.location.lower())
