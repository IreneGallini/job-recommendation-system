import requests
import filters
from scrapers.base import Posting

_MAX_MESSAGE_LEN = 1900  # Discord's cap is 2000; leave a margin.
_USER_AGENT = "internship-scraper/1.0 (+https://github.com/)"


def send_new_postings(webhook_url: str, postings: list[Posting]) -> None:
    if not webhook_url:
        print("Discord: DISCORD_WEBHOOK_URL not set, skipping notification.")
        return
    if not postings:
        return

    ordered = sorted(postings, key=_sort_key)
    lines = [_format_line(p) for p in ordered]

    header = f"**{len(ordered)} new internship posting(s):**"
    for chunk in _batch(lines, header):
        response = requests.post(
            webhook_url,
            json={"content": chunk},
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()


def _sort_key(p: Posting) -> tuple[int, int, str]:
    region = filters.region_for_posting(p)
    region_rank = 0 if region == filters.MILAN else 1
    priority_rank = 0 if p.priority == "high" else 1
    return (region_rank, priority_rank, p.company)


def _format_line(p: Posting) -> str:
    flag = "⭐ " if p.priority == "high" or filters.region_for_posting(p) == filters.MILAN else ""
    return (
        f"{flag}**{p.company}** — {p.role}\n"
        f"{p.location} · {p.source}\n"
        f"{p.link}"
    )


def _batch(lines: list[str], header: str) -> list[str]:
    chunks = []
    current = header
    for line in lines:
        candidate = f"{current}\n\n{line}"
        if len(candidate) > _MAX_MESSAGE_LEN:
            chunks.append(current)
            current = line
        else:
            current = candidate
    chunks.append(current)
    return chunks
