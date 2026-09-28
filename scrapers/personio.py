import re
import requests
from .base import Posting, Scraper

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"
_POSITION_RE = re.compile(r"<position>(.*?)</position>", re.DOTALL)
_OFFICE_RE = re.compile(r"<office>(.*?)</office>", re.DOTALL)


class PersonioScraper(Scraper):
    """Public, unauthenticated Personio XML job feed.

    `host` is per-tenant: most careers sites are on
    `{slug}.jobs.personio.de` but some are `.com` instead — check the
    company's actual careers page hostname before adding it.
    """

    def __init__(
        self,
        slug: str,
        company_name: str,
        category: str,
        priority: str,
        host_suffix: str = "jobs.personio.de",
    ):
        self.slug = slug
        self.company_name = company_name
        self.category = category
        self.priority = priority
        self.host_suffix = host_suffix

    def get_postings(self) -> list[Posting]:
        url = f"https://{self.slug}.{self.host_suffix}/xml?language=en"
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
        response.raise_for_status()
        return [
            posting
            for block in _POSITION_RE.findall(response.text)
            if (posting := self._to_posting(block)) is not None
        ]

    def _to_posting(self, block: str) -> Posting | None:
        job_id = self._field(block, "id")
        title = self._field(block, "name")
        if not job_id or not title:
            return None

        offices = list(dict.fromkeys(o.strip() for o in _OFFICE_RE.findall(block) if o.strip()))

        return Posting(
            company=self.company_name,
            role=title,
            location="; ".join(offices),
            link=f"https://{self.slug}.{self.host_suffix}/job/{job_id}?language=en",
            date_added="",
            source="Personio",
            category=self.category,
            priority=self.priority,
            ats="personio",
        )

    @staticmethod
    def _field(block: str, tag: str) -> str:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.DOTALL)
        return match.group(1).strip() if match else ""
