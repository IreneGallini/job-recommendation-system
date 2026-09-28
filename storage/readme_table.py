import os
import filters
from scrapers.base import Posting

TABLE_START = "<!-- POSTINGS_TABLE_START -->"
TABLE_END = "<!-- POSTINGS_TABLE_END -->"

_SECTIONS = [
    (filters.MILAN, "Milan"),
    (filters.ITALY, "Rest of Italy"),
    (filters.EUROPE, "Rest of Europe"),
    (filters.REMOTE_EUROPE, "Remote (Europe)"),
]


def write_postings_table(readme_path: str, postings: list[Posting]) -> None:
    table = _render_sections(postings)
    section = f"{TABLE_START}\n{table}\n{TABLE_END}"

    existing = ""
    if os.path.exists(readme_path):
        with open(readme_path, encoding="utf-8") as f:
            existing = f.read()

    if TABLE_START in existing and TABLE_END in existing:
        before = existing.split(TABLE_START)[0]
        after = existing.split(TABLE_END)[1]
        content = before + section + after
    else:
        separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
        content = f"{existing}{separator}## Current Postings\n\n{section}\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


def _render_sections(postings: list[Posting]) -> str:
    if not postings:
        return "_No postings found yet._"

    by_region: dict[str, list[Posting]] = {region: [] for region, _ in _SECTIONS}
    for p in postings:
        by_region.setdefault(filters.region_for_posting(p), []).append(p)

    blocks = []
    for region, heading in _SECTIONS:
        rows = by_region.get(region, [])
        if not rows:
            continue
        blocks.append(f"### {heading}\n\n{_render_table(rows)}")
    return "\n\n".join(blocks) if blocks else "_No postings found yet._"


def _render_table(postings: list[Posting]) -> str:
    rows = sorted(postings, key=lambda p: p.first_seen or p.date_added, reverse=True)
    lines = [
        "| Priority | Company | Role | Location | Category | Source | Found | Apply |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in rows:
        flag = "⭐" if p.priority == "high" else ""
        lines.append(
            f"| {flag} | {_escape(p.company)} | {_escape(p.role)} | {_escape(p.location)} "
            f"| {_escape(p.category)} | {_escape(p.source)} | {_escape(p.first_seen or p.date_added)} "
            f"| [Apply]({p.link}) |"
        )
    return "\n".join(lines)


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
