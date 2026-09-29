import filters
from .base import Posting, Scraper, retrying_session

_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"
_PAGE_LIMIT = 100
# Bosch alone is ~48 pages; one read timeout used to drop the whole company.
_session = retrying_session()


class SmartRecruitersScraper(Scraper):
    """Public, unauthenticated SmartRecruiters postings API.

    `company_identifier` is case-sensitive and often differs from the
    company's display name (e.g. Bosch's is "BoschGroup") — read it off the
    company's actual jobs.smartrecruiters.com URL, don't guess.
    """

    def __init__(self, company_identifier: str, company_name: str, category: str, priority: str):
        self.company_identifier = company_identifier
        self.company_name = company_name
        self.category = category
        self.priority = priority

    def get_postings(self) -> list[Posting]:
        url = f"https://api.smartrecruiters.com/v1/companies/{self.company_identifier}/postings"
        postings = []
        offset = 0
        while True:
            response = _session.get(
                url,
                params={"limit": _PAGE_LIMIT, "offset": offset},
                headers={"User-Agent": _USER_AGENT},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            batch = data.get("content", [])
            if not batch:
                break
            postings.extend(self._to_posting(p) for p in batch)
            offset += _PAGE_LIMIT
            if offset >= data.get("totalFound", 0):
                break
        return postings

    def fetch_description(self, posting: Posting) -> str:
        posting_id = posting.link.rstrip("/").rsplit("/", 1)[-1]
        response = _session.get(
            f"https://api.smartrecruiters.com/v1/companies/{self.company_identifier}/postings/{posting_id}",
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        sections = (response.json().get("jobAd") or {}).get("sections") or {}
        return "\n".join(
            (sections.get(key) or {}).get("text", "")
            for key in ("jobDescription", "qualifications", "additionalInformation")
        )

    def _to_posting(self, posting: dict) -> Posting:
        location = posting.get("location") or {}
        city = location.get("city", "")
        country = filters.iso2_to_country_name(location.get("country", ""))
        loc_text = f"{city}, {country}".strip(", ") if (city or country) else ""
        posting_id = posting.get("id", "")
        return Posting(
            company=self.company_name,
            role=posting.get("name", ""),
            location=loc_text,
            link=f"https://jobs.smartrecruiters.com/{self.company_identifier}/{posting_id}",
            date_added=posting.get("releasedDate", ""),
            source="SmartRecruiters",
            category=self.category,
            priority=self.priority,
            ats="smartrecruiters",
        )
