import requests
from .base import Posting, Scraper

_JOBS_URL = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
_SITE_BASE = "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"
_PAGE_LIMIT = 20
_MAX_OFFSET = 200

_KEYWORDS = (
    "software engineer",
    "data science",
    "data analyst",
    "data engineer",
    "ml engineer",
    "ai engineer",
)
_EXCLUDE = ("new college grad", "college graduate")


class NvidiaCareersScraper(Scraper):
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
            _JOBS_URL,
            json={
                "appliedFacets": {},
                "limit": _PAGE_LIMIT,
                "offset": offset,
                "searchText": "2027 intern",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("jobPostings", [])

    @staticmethod
    def _to_posting(job: dict) -> Posting | None:
        title = job.get("title", "")
        title_lower = title.lower()

        if "intern" not in title_lower:
            return None
        if any(term in title_lower for term in _EXCLUDE):
            return None
        if "2027" not in title:
            return None
        if not any(keyword in title_lower for keyword in _KEYWORDS):
            return None

        external_path = job.get("externalPath", "")
        if not external_path:
            return None

        return Posting(
            company="NVIDIA",
            role=title,
            location=job.get("locationsText", ""),
            link=_SITE_BASE + external_path,
            date_added=job.get("postedOn", ""),
            source="NVIDIA Careers",
        )
