import re
import requests
from .base import Posting, Scraper

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_CELL_RE = re.compile(r"<td>(.*?)</td>", re.DOTALL)
_ANCHOR_TEXT_RE = re.compile(r"<a[^>]*>([^<]+)</a>")
_HREF_RE = re.compile(r'href="([^"]+)"')
_TAG_RE = re.compile(r"<[^>]+>")
_DETAILS_RE = re.compile(r"<details>.*?</summary>(.*?)</details>", re.DOTALL)


class SimplifyGitHubScraper(Scraper):
    def __init__(self, readme_url: str):
        self.readme_url = readme_url

    def get_postings(self) -> list[Posting]:
        response = requests.get(self.readme_url, timeout=30)
        response.raise_for_status()
        return self._parse(response.text)

    def _parse(self, markdown: str) -> list[Posting]:
        postings = []
        for row in _ROW_RE.findall(markdown):
            posting = self._parse_row(row)
            if posting:
                postings.append(posting)
        return postings

    def _parse_row(self, row: str) -> Posting | None:
        cells = _CELL_RE.findall(row)
        if len(cells) < 5:
            return None

        company_cell, role_cell, location_cell, link_cell, age_cell = cells[:5]

        # Skip sub-role rows (company cell is just "↳")
        if self._strip_tags(company_cell).strip() == "↳":
            return None

        company = self._extract_anchor_text(company_cell)
        if not company:
            return None

        role = self._strip_tags(role_cell).strip()
        location = self._extract_location(location_cell)

        link = self._extract_href(link_cell)
        if not link:
            return None

        age = self._strip_tags(age_cell).strip()

        return Posting(
            company=company,
            role=role,
            location=location,
            link=link,
            date_added=age,
            source="SimplifyJobs",
        )

    @staticmethod
    def _extract_anchor_text(cell: str) -> str:
        match = _ANCHOR_TEXT_RE.search(cell)
        if match:
            return match.group(1).strip()
        return SimplifyGitHubScraper._strip_tags(cell).strip()

    @staticmethod
    def _extract_location(cell: str) -> str:
        details_match = _DETAILS_RE.search(cell)
        body = details_match.group(1) if details_match else cell
        parts = [
            SimplifyGitHubScraper._strip_tags(part).strip()
            for part in body.split("<br>")
        ]
        return "; ".join(p for p in parts if p)

    @staticmethod
    def _extract_href(cell: str) -> str | None:
        match = _HREF_RE.search(cell)
        return match.group(1) if match else None

    @staticmethod
    def _strip_tags(text: str) -> str:
        return _TAG_RE.sub("", text)
