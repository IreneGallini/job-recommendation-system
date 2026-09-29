import requests
from .base import Posting, Scraper

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"


class LeverScraper(Scraper):
    """Public, unauthenticated Lever postings API.

    `host` defaults to `api.lever.co`; some companies (EU data residency)
    are hosted on `api.eu.lever.co` instead — check the company's careers
    page network requests to tell which one before adding it to
    companies.yaml.
    """

    def __init__(
        self,
        slug: str,
        company_name: str,
        category: str,
        priority: str,
        host: str = "api.lever.co",
    ):
        self.slug = slug
        self.company_name = company_name
        self.category = category
        self.priority = priority
        self.host = host

    def get_postings(self) -> list[Posting]:
        url = f"https://{self.host}/v0/postings/{self.slug}?mode=json"
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
        response.raise_for_status()
        postings = response.json()
        if not isinstance(postings, list):
            return []
        return [self._to_posting(p) for p in postings]

    def _to_posting(self, posting: dict) -> Posting:
        categories = posting.get("categories") or {}
        description = "\n".join(
            [posting.get("descriptionPlain", "")]
            + [f"{item.get('text', '')}\n{item.get('content', '')}" for item in posting.get("lists") or []]
            + [posting.get("additionalPlain", "")]
        )
        return Posting(
            company=self.company_name,
            role=posting.get("text", ""),
            location=categories.get("location", ""),
            link=posting.get("hostedUrl", ""),
            date_added=str(posting.get("createdAt", "")),
            source="Lever",
            category=self.category,
            priority=self.priority,
            ats="lever",
            description=description,
        )
