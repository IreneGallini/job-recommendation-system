import requests
from .base import Posting, Scraper

_JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
_JOB_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"


class GreenhouseScraper(Scraper):
    """Public, unauthenticated Greenhouse job-board API.

    Note: `boards-api.greenhouse.io` is the correct API host even for
    companies whose public careers *page* is served from
    `job-boards.eu.greenhouse.io` (EU data-residency tenants, e.g. Scalapay)
    — the API host doesn't change, only the UI domain does.

    The list call skips descriptions (`content=false`; Stripe alone has
    700+ jobs) — `fetch_description` gets them per job, only for postings
    that survive filtering.
    """

    def __init__(self, slug: str, company_name: str, category: str, priority: str):
        self.slug = slug
        self.company_name = company_name
        self.category = category
        self.priority = priority
        self._job_ids: dict[str, int] = {}

    def get_postings(self) -> list[Posting]:
        response = requests.get(
            _JOBS_URL.format(slug=self.slug),
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        return [self._to_posting(job) for job in jobs]

    def fetch_description(self, posting: Posting) -> str:
        job_id = self._job_ids.get(posting.link)
        if job_id is None:
            return ""
        response = requests.get(
            _JOB_URL.format(slug=self.slug, job_id=job_id),
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("content", "")

    def _to_posting(self, job: dict) -> Posting:
        link = job.get("absolute_url", "")
        self._job_ids[link] = job.get("id")
        return Posting(
            company=self.company_name,
            role=job.get("title", ""),
            location=(job.get("location") or {}).get("name", ""),
            link=link,
            # first_published is the real posting date; updated_at changes on every edit.
            date_added=job.get("first_published") or job.get("updated_at", ""),
            source="Greenhouse",
            category=self.category,
            priority=self.priority,
            ats="greenhouse",
        )
