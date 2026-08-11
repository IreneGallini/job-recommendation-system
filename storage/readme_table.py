import os
from scrapers.base import Posting

TABLE_START = "<!-- POSTINGS_TABLE_START -->"
TABLE_END = "<!-- POSTINGS_TABLE_END -->"


def write_postings_table(readme_path: str, postings: list[Posting]) -> None:
    table = _render_table(postings)
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


def _render_table(postings: list[Posting]) -> str:
    if not postings:
        return "_No postings found yet._"

    rows = sorted(postings, key=lambda p: p.date_added, reverse=True)
    lines = [
        "| Company | Role | Location | Source | Found | Apply |",
        "|---|---|---|---|---|---|",
    ]
    for p in rows:
        lines.append(
            f"| {_escape(p.company)} | {_escape(p.role)} | {_escape(p.location)} "
            f"| {_escape(p.source)} | {_escape(p.date_added)} | [Apply]({p.link}) |"
        )
    return "\n".join(lines)


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
