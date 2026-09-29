from datetime import datetime

import requests
from .base import Posting, Scraper

_SEARCH_URL = "https://www.amazon.jobs/en/search.json"
_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"
_PAGE_LIMIT = 100

# amazon.jobs filters by ISO-3166 alpha-3 country; one search per eligible
# country keeps the result set small (a global "intern" search is mostly US).
_COUNTRIES = {
    "ITA": "Italy", "CHE": "Switzerland", "FRA": "France", "DEU": "Germany",
    "DNK": "Denmark", "NOR": "Norway", "SWE": "Sweden", "FIN": "Finland",
    "ESP": "Spain", "PRT": "Portugal", "NLD": "Netherlands", "BEL": "Belgium",
    "AUT": "Austria", "IRL": "Ireland",
}


class AmazonScraper(Scraper):
    """amazon.jobs' public, unauthenticated search JSON (the same endpoint
    its own search page calls). Amazon doesn't use a third-party ATS, hence
    a dedicated scraper. Descriptions come back in the search response."""

    def __init__(self, company_name: str, category: str, priority: str, search_text: str = "intern"):
        self.company_name = company_name
        self.category = category
        self.priority = priority
        self.search_text = search_text

    def get_postings(self) -> list[Posting]:
        postings = {}
        for code, country in _COUNTRIES.items():
            offset = 0
            while True:
                response = requests.get(
                    _SEARCH_URL,
                    params={
                        "base_query": self.search_text,
                        "country": code,
                        "result_limit": _PAGE_LIMIT,
                        "offset": offset,
                    },
                    headers={"User-Agent": _USER_AGENT},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                jobs = data.get("jobs", [])
                for job in jobs:
                    posting = self._to_posting(job, country)
                    postings.setdefault(posting.link, posting)
                offset += _PAGE_LIMIT
                if not jobs or offset >= data.get("hits", 0):
                    break
        return list(postings.values())

    def _to_posting(self, job: dict, country: str) -> Posting:
        city = job.get("city", "")
        return Posting(
            company=self.company_name,
            role=job.get("title", ""),
            location=f"{city}, {country}" if city else country,
            link=f"https://www.amazon.jobs{job.get('job_path', '')}",
            date_added=_parse_date(job.get("posted_date", "")),
            source="Amazon",
            category=self.category,
            priority=self.priority,
            ats="amazon",
            description="\n".join(
                job.get(key, "") or ""
                for key in ("description", "basic_qualifications", "preferred_qualifications")
            ),
        )


def _parse_date(text: str) -> str:
    """"August 28, 2026" -> "2026-08-28"."""
    try:
        return datetime.strptime(text.strip(), "%B %d, %Y").date().isoformat()
    except ValueError:
        return ""
