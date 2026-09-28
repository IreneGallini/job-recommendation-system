import requests
from .base import Posting, Scraper

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"


class AshbyScraper(Scraper):
    """Public, unauthenticated Ashby job-board API."""

    def __init__(self, slug: str, company_name: str, category: str, priority: str):
        self.slug = slug
        self.company_name = company_name
        self.category = category
        self.priority = priority

    def get_postings(self) -> list[Posting]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.slug}"
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        return [self._to_posting(job) for job in jobs]

    def _to_posting(self, job: dict) -> Posting:
        locations = [job.get("location", "")]
        for extra in job.get("secondaryLocations") or []:
            loc = extra.get("location")
            if loc:
                locations.append(loc)
        return Posting(
            company=self.company_name,
            role=job.get("title", ""),
            location="; ".join(loc for loc in locations if loc),
            link=job.get("jobUrl", ""),
            date_added=job.get("publishedAt", ""),
            source="Ashby",
            category=self.category,
            priority=self.priority,
            ats="ashby",
        )
