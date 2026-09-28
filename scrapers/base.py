from abc import ABC, abstractmethod
from dataclasses import dataclass


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


class Scraper(ABC):
    @abstractmethod
    def get_postings(self) -> list[Posting]:
        ...
