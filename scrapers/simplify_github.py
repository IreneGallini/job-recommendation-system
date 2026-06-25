import re
import requests
from .base import Posting, Scraper


class SimplifyGitHubScraper(Scraper):
    def __init__(self, readme_url: str):
        self.readme_url = readme_url

    def get_postings(self) -> list[Posting]:
        response = requests.get(self.readme_url, timeout=30)
        response.raise_for_status()
        return self._parse(response.text)

    def _parse(self, markdown: str) -> list[Posting]:
        postings = []
        for line in markdown.splitlines():
            posting = self._parse_row(line)
            if posting:
                postings.append(posting)
        return postings

    def _parse_row(self, row: str) -> Posting | None:
        if not row.startswith("|"):
            return None

        cells = [c.strip() for c in row.split("|")]
        # cells[0] empty, cells[1..5] data, cells[6] empty
        if len(cells) < 6:
            return None

        company_cell, role_cell, location_cell, link_cell = (
            cells[1], cells[2], cells[3], cells[4],
        )
        date_cell = cells[5] if len(cells) > 5 else ""

        # Skip header and separator rows
        if "---" in company_cell or company_cell.lower() == "company":
            return None

        # Skip sub-role rows (start with ↳)
        if company_cell.startswith("↳") or not company_cell:
            return None

        # Skip rows with no open link (locked postings show 🔒)
        if "🔒" in link_cell:
            return None

        company = self._extract_text(company_cell)
        if not company:
            return None

        role = self._strip_tags(role_cell)
        location = self._strip_tags(location_cell)

        link = self._extract_href(link_cell) or self._extract_md_link(link_cell)
        if not link:
            return None

        date = self._strip_tags(date_cell)

        return Posting(company=company, role=role, location=location, link=link, date_added=date)

    @staticmethod
    def _extract_text(cell: str) -> str:
        # Handles **[Company](url)** and **Company**
        match = re.search(r"\[([^\]]+)\]", cell)
        if match:
            return match.group(1).strip()
        return re.sub(r"[*_`]", "", cell).strip()

    @staticmethod
    def _strip_tags(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()

    @staticmethod
    def _extract_href(cell: str) -> str | None:
        match = re.search(r'href=["\']([^"\']+)["\']', cell)
        return match.group(1) if match else None

    @staticmethod
    def _extract_md_link(cell: str) -> str | None:
        match = re.search(r"\[.*?\]\(([^)]+)\)", cell)
        return match.group(1) if match else None
