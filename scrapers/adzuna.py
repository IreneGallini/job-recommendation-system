import sys
import time
from urllib.parse import urlsplit, urlunsplit

import filters

from .base import Posting, Scraper, retrying_session

_SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
_PAGE_SIZE = 50  # Adzuna's maximum
# Free tier allows 25 requests/minute; stay safely under it.
_SECONDS_BETWEEN_REQUESTS = 2.6

# Adzuna covers 8 of the 14 eligible countries (no DK, NO, SE, FI, PT, IE).
# Internship terms per country, main one first; Italy first so it gets the
# request budget before anything else.
_SEARCHES = {
    "it": ("Italy", ("stage", "tirocinio", "internship", "intern", "stagista")),
    "ch": ("Switzerland", ("internship", "intern", "praktikum", "stage")),
    "fr": ("France", ("stage", "stagiaire", "internship")),
    "de": ("Germany", ("praktikum", "praktikant", "internship")),
    "es": ("Spain", ("prácticas", "becario", "internship")),
    "nl": ("Netherlands", ("stage", "stagiair", "internship")),
    "be": ("Belgium", ("stage", "stagiair", "internship")),
    "at": ("Austria", ("praktikum", "praktikant", "internship")),
}




def queries(terms: tuple[str, ...]) -> list[dict]:
    """A bare title search is far too broad (2,640 Italian "stage" ads, mostly
    reception/accounting), so searches are narrowed to target-role slices
    small enough to fetch completely:
      - every term within Adzuna's IT category
      - the main term within its science category (comp-chem/pharma interest)
      - "<term> data" titles, for data roles filed under other categories
    """
    main_term = terms[0]
    return (
        [{"title_only": term, "category": "it-jobs"} for term in terms]
        + [{"title_only": main_term, "category": "scientific-qa-jobs"}]
        + [{"title_only": f"{term} data"} for term in terms[:2]]
    )


class AdzunaScraper(Scraper):
    """Adzuna job-aggregator search API (free developer key). Covers
    employers that aren't on the watchlist or on a supported ATS. The free
    tier is capped at 2,500 requests/month, so main.py only runs this once a
    day and `max_requests` bounds each run. Descriptions are only snippets,
    so there's nothing to fetch per posting."""

    company_name = "Adzuna"

    def __init__(self, app_id: str, app_key: str, max_pages_per_query: int, max_requests: int):
        self.app_id = app_id
        self.app_key = app_key
        self.max_pages_per_query = max_pages_per_query
        self.max_requests = max_requests
        self.requests_made = 0

    def get_postings(self) -> list[Posting]:
        session = retrying_session()
        postings = {}
        for code, (country, terms) in _SEARCHES.items():
            for query in queries(terms):
                for page in range(1, self.max_pages_per_query + 1):
                    if self.requests_made >= self.max_requests:
                        print(f"Adzuna: request budget ({self.max_requests}) reached.", file=sys.stderr)
                        return list(postings.values())
                    if self.requests_made:
                        time.sleep(_SECONDS_BETWEEN_REQUESTS)
                    self.requests_made += 1
                    response = session.get(
                        _SEARCH_URL.format(country=code, page=page),
                        params={
                            "app_id": self.app_id,
                            "app_key": self.app_key,
                            **query,
                            "results_per_page": _PAGE_SIZE,
                            "sort_by": "date",
                            "content-type": "application/json",
                        },
                        timeout=30,
                    )
                    response.raise_for_status()
                    results = response.json().get("results", [])
                    for job in results:
                        posting = to_posting(job, country)
                        postings.setdefault(posting.link, posting)
                    if len(results) < _PAGE_SIZE:
                        break
        return list(postings.values())


def to_posting(job: dict, country: str) -> Posting:
    # `area` runs from country down to town, e.g. ["Italia", "Lombardia",
    # "Milano", "Segrate"]; only a third level or deeper names a town.
    area = (job.get("location") or {}).get("area") or []
    city = area[-1] if len(area) >= 3 else ""
    title = (job.get("title") or "").strip()
    if not city:
        # Region-only ad ("Lombardia"): titles often name the city
        # ("... - Milano"), which matters for the Milan/Turin ranking.
        match = filters.city_in_text(title)
        if match and match[1] == country:
            city = match[0]
    return Posting(
        company=((job.get("company") or {}).get("display_name") or "Unknown").strip(),
        role=title,
        location=f"{city}, {country}" if city else country,
        link=_stable_link(job),
        date_added=(job.get("created") or "")[:10],
        source="Adzuna",
        ats="adzuna",
        description=job.get("description") or "",
    )


def _stable_link(job: dict) -> str:
    """redirect_url carries per-request tracking params; dedup is by link,
    so keep only scheme/host/path (which embeds the ad id)."""
    url = job.get("redirect_url") or ""
    if not url:
        return f"adzuna:{job.get('id', '')}"
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
