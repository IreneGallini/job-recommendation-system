import requests
from .base import Posting, Scraper

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"
_PAGE_LIMIT = 20
_MAX_OFFSET = 200


class WorkdayScraper(Scraper):
    """Public, unauthenticated Workday CxS job-search API.

    Generalized from an NVIDIA-specific scraper. URL pattern:
    https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    `wd_host` is the "wdN" segment (e.g. "wd5", "wd3") and `site` is the
    external career site's path segment — both are per-tenant and must be
    read off the company's actual careers URL, not guessed.
    """

    def __init__(
        self,
        tenant: str,
        wd_host: str,
        site: str,
        search_text: str,
        company_name: str,
        category: str,
        priority: str,
    ):
        self.tenant = tenant
        self.wd_host = wd_host
        self.site = site
        self.search_text = search_text
        self.company_name = company_name
        self.category = category
        self.priority = priority
        self.jobs_url = (
            f"https://{tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        )
        self.site_base = f"https://{tenant}.{wd_host}.myworkdayjobs.com/en-US/{site}"

    def get_postings(self) -> list[Posting]:
        postings = []
        offset = 0
        while offset < _MAX_OFFSET:
            batch = self._fetch_page(offset)
            if not batch:
                break
            for job in batch:
                posting = self._to_posting(job)
                if posting:
                    postings.append(posting)
            offset += _PAGE_LIMIT
        return postings

    def _fetch_page(self, offset: int) -> list[dict]:
        response = requests.post(
            self.jobs_url,
            json={
                "appliedFacets": {},
                "limit": _PAGE_LIMIT,
                "offset": offset,
                "searchText": self.search_text,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("jobPostings", [])

    def _to_posting(self, job: dict) -> Posting | None:
        external_path = job.get("externalPath", "")
        if not external_path:
            return None
        return Posting(
            company=self.company_name,
            role=job.get("title", ""),
            location=job.get("locationsText", ""),
            link=self.site_base + external_path,
            date_added=job.get("postedOn", ""),
            source="Workday",
            category=self.category,
            priority=self.priority,
            ats="workday",
        )
