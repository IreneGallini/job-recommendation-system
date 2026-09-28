import requests
from .base import Posting, Scraper

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"


class WorkableScraper(Scraper):
    """Public, unauthenticated Workable jobs widget API."""

    def __init__(self, slug: str, company_name: str, category: str, priority: str):
        self.slug = slug
        self.company_name = company_name
        self.category = category
        self.priority = priority

    def get_postings(self) -> list[Posting]:
        url = f"https://apply.workable.com/api/v1/widget/accounts/{self.slug}"
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        return [self._to_posting(job) for job in jobs]

    def _to_posting(self, job: dict) -> Posting:
        city = job.get("city", "")
        country = job.get("country", "")
        loc_text = f"{city}, {country}".strip(", ") if (city or country) else ""
        return Posting(
            company=self.company_name,
            role=job.get("title", ""),
            location=loc_text,
            link=job.get("application_url", job.get("shortlink", "")),
            date_added=job.get("published_on", ""),
            source="Workable",
            category=self.category,
            priority=self.priority,
            ats="workable",
        )
