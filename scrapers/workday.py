import re

from .base import Posting, Scraper, retrying_session

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"

# Workday resets connections when several tenants on the same wdN host are
# hit at once (main.py scrapes sources concurrently); retry with backoff
# instead of losing the whole company for this run.
_session = retrying_session()
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
        search_text: str | list[str],
        company_name: str,
        category: str,
        priority: str,
    ):
        self.tenant = tenant
        self.wd_host = wd_host
        self.site = site
        # A list runs one search per entry (deduped by link). Big global
        # tenants hit _MAX_OFFSET on US postings with a bare "intern", so
        # companies.yaml pairs it with e.g. "intern Italy" — Workday's
        # full-text search matches location names too.
        self.search_texts = [search_text] if isinstance(search_text, str) else list(search_text)
        self.company_name = company_name
        self.category = category
        self.priority = priority
        self.jobs_url = (
            f"https://{tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        )
        self.site_base = f"https://{tenant}.{wd_host}.myworkdayjobs.com/en-US/{site}"

    def get_postings(self) -> list[Posting]:
        postings = {}
        for search_text in self.search_texts:
            offset = 0
            while offset < _MAX_OFFSET:
                batch = self._fetch_page(search_text, offset)
                if not batch:
                    break
                for job in batch:
                    posting = self._to_posting(job)
                    if posting:
                        postings.setdefault(posting.link, posting)
                offset += _PAGE_LIMIT
        return list(postings.values())

    def _fetch_page(self, search_text: str, offset: int) -> list[dict]:
        response = _session.post(
            self.jobs_url,
            json={
                "appliedFacets": {},
                "limit": _PAGE_LIMIT,
                "offset": offset,
                "searchText": search_text,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("jobPostings", [])

    def fetch_description(self, posting: Posting) -> str:
        external_path = posting.link.removeprefix(self.site_base)
        response = _session.get(
            self.jobs_url.removesuffix("/jobs") + external_path,
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        return (response.json().get("jobPostingInfo") or {}).get("jobDescription", "")

    def _to_posting(self, job: dict) -> Posting | None:
        external_path = job.get("externalPath", "")
        if not external_path:
            return None
        location = job.get("locationsText") or ""
        if not location.strip() or re.fullmatch(r"\d+\s+locations?", location.strip(), re.IGNORECASE):
            # Multi-location jobs only say "2 Locations" (and some tenants,
            # e.g. Accenture, omit it entirely); the primary location is
            # still in the path ("/job/Germany-Munich/...").
            parts = external_path.split("/")
            location = parts[2].replace("-", " ") if len(parts) > 2 else location
        return Posting(
            company=self.company_name,
            role=job.get("title", ""),
            location=location,
            link=self.site_base + external_path,
            date_added=job.get("postedOn", ""),
            source="Workday",
            category=self.category,
            priority=self.priority,
            ats="workday",
        )
