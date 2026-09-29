import os
import config
import filters
import ranking
from scrapers.base import Posting

TABLE_START = "<!-- POSTINGS_TABLE_START -->"
TABLE_END = "<!-- POSTINGS_TABLE_END -->"

_SECTIONS = [
    (filters.MILAN, "Milan area"),
    (filters.TURIN, "Turin area"),
    (filters.ITALY, "Rest of Italy"),
    (filters.EUROPE, "Rest of Europe"),
    (filters.REMOTE_EUROPE, "Remote (Europe)"),
]

_SUMMER_LABELS = {"yes": "✅ summer", "unknown": "❔", "no": "❌ not summer"}


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
    """Target-role postings that are still open, ranked by recommendation
    score within each region. Postings that clearly don't fit the summer go
    in one collapsed block at the end; the full collection (every eligible
    internship) lives on the site."""
    visible = ranking.rank(ranking.active(
        p for p in ranking.current_cycle(postings) if p.role_match
    ))
    header = (
        f"Ranked by recommendation score. Triage (applied / ineligible) and the full "
        f"collection of every eligible internship are on the **[site]({config.SITE_URL})**."
    )
    if not visible:
        return f"{header}\n\n_No postings found yet._"

    fits = [p for p in visible if p.summer_fit != "no"]
    no_fit = [p for p in visible if p.summer_fit == "no"]

    by_region: dict[str, list[Posting]] = {region: [] for region, _ in _SECTIONS}
    for p in fits:
        by_region.setdefault(filters.region_for_posting(p), []).append(p)

    blocks = [header]
    for region, heading in _SECTIONS:
        rows = by_region.get(region, [])
        if rows:
            blocks.append(f"### {heading}\n\n{_render_table(rows)}")
    if no_fit:
        blocks.append(
            f"<details>\n<summary>Not a summer fit ({len(no_fit)}) — 5+ months or "
            f"starts Sept–March</summary>\n\n{_render_table(no_fit)}\n\n</details>"
        )
    return "\n\n".join(blocks)


def _render_table(postings: list[Posting]) -> str:
    lines = [
        "| Score | Company | Role | Location | Summer | Posted | Apply |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in postings:
        flag = "⭐ " if p.priority == "high" else ""
        summer = _SUMMER_LABELS.get(p.summer_fit, "❔")
        if p.duration_months:
            summer += f" ({p.duration_months} mo)"
        lines.append(
            f"| {ranking.score(p)} | {flag}{_escape(p.company)} | {_escape(p.role)} "
            f"| {_escape(p.location)} | {summer} | {ranking.effective_date(p)} "
            f"| [Apply]({p.link}) |"
        )
    return "\n".join(lines)


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
