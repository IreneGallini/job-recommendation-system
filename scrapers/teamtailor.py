import requests
import filters
from .base import Posting, Scraper

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"


class TeamtailorScraper(Scraper):
    """Public, unauthenticated Teamtailor per-tenant JSON job feed
    (`{slug}.teamtailor.com/jobs.json`) — a JSON Feed exposed for RSS-style
    consumption, distinct from Teamtailor's official Public API which needs
    a per-company API key. No key needed for this endpoint."""

    def __init__(self, slug: str, company_name: str, category: str, priority: str):
        self.slug = slug
        self.company_name = company_name
        self.category = category
        self.priority = priority

    def get_postings(self) -> list[Posting]:
        url = f"https://{self.slug}.teamtailor.com/jobs.json"
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
        response.raise_for_status()
        items = response.json().get("items", [])
        return [self._to_posting(item) for item in items]

    def _to_posting(self, item: dict) -> Posting:
        job_posting = item.get("_jobposting") or {}
        locations = []
        for place in job_posting.get("jobLocation") or []:
            address = place.get("address") or {}
            city = address.get("addressLocality", "")
            country = filters.iso2_to_country_name(address.get("addressCountry", ""))
            if city or country:
                locations.append(f"{city}, {country}".strip(", "))
        return Posting(
            company=self.company_name,
            role=item.get("title", ""),
            location="; ".join(locations),
            link=item.get("url", ""),
            date_added=item.get("date_published", ""),
            source="Teamtailor",
            category=self.category,
            priority=self.priority,
            ats="teamtailor",
            description=item.get("content_html", ""),
        )
