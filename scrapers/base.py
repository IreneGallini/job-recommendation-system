from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def retrying_session() -> requests.Session:
    """Session that retries connection resets, read timeouts and 429/5xx
    with exponential backoff (2s, 4s, 8s...). For paginated sources where a
    single flaky request would otherwise drop the whole company for a run."""
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,  # retry POST too: Workday's jobs search is read-only
    )))
    return session


@dataclass
class Posting:
    company: str
    role: str
    location: str
    link: str
    date_added: str
    source: str
    country: str = ""
    city: str = ""
    category: str = "unknown"
    priority: str = "normal"
    ats: str = ""
    first_seen: str = ""
    posted_date: str = ""
    last_seen: str = ""
    role_match: bool = True
    summer_program: bool = False
    duration_months: str = ""
    start_hint: str = ""
    summer_fit: str = "unknown"
    degree_req: str = "unknown"
    # True once the description was fetched (or the source has none to
    # fetch); failed fetches are retried on later runs.
    described: bool = False
    # In-memory only (never written to the CSV): used by enrich.py to parse
    # duration/start/degree requirements, then discarded.
    description: str = ""


class Scraper(ABC):
    @abstractmethod
    def get_postings(self) -> list[Posting]:
        ...

    def fetch_description(self, posting: Posting) -> str:
        """Fetch a posting's description text when the list endpoint didn't
        include it. Only called for new postings that already passed
        filtering, so it's a handful of requests per run at most."""
        return posting.description
