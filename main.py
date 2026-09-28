import json
import os
import sys

import yaml

import config
import filters
from scrapers.simplify_github import SimplifyGitHubScraper
from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper
from scrapers.ashby import AshbyScraper
from scrapers.workday import WorkdayScraper
from scrapers.smartrecruiters import SmartRecruitersScraper
from scrapers.personio import PersonioScraper
from scrapers.workable import WorkableScraper
from scrapers.teamtailor import TeamtailorScraper
from storage.csv_store import load_seen_links, load_all_postings, append_new_postings
from storage.readme_table import write_postings_table
from notifications.discord import send_new_postings

_LAST_COUNTS_PATH = "last_run_counts.json"

_ATS_BUILDERS = {
    "greenhouse": lambda c: GreenhouseScraper(c["slug"], c["name"], c["category"], c["priority"]),
    "lever": lambda c: LeverScraper(
        c["slug"], c["name"], c["category"], c["priority"], host=c.get("host", "api.lever.co")
    ),
    "ashby": lambda c: AshbyScraper(c["slug"], c["name"], c["category"], c["priority"]),
    "workday": lambda c: WorkdayScraper(
        c["tenant"], c["wd_host"], c["site"], c.get("search_text", "intern"),
        c["name"], c["category"], c["priority"],
    ),
    "smartrecruiters": lambda c: SmartRecruitersScraper(
        c["company_identifier"], c["name"], c["category"], c["priority"]
    ),
    "personio": lambda c: PersonioScraper(
        c["slug"], c["name"], c["category"], c["priority"],
        host_suffix=c.get("host_suffix", "jobs.personio.de"),
    ),
    "workable": lambda c: WorkableScraper(c["slug"], c["name"], c["category"], c["priority"]),
    "teamtailor": lambda c: TeamtailorScraper(c["slug"], c["name"], c["category"], c["priority"]),
}


def build_scrapers() -> list:
    scrapers = [SimplifyGitHubScraper(config.SIMPLIFY_README_URL)]

    companies = []
    if os.path.exists(config.COMPANIES_YAML_PATH):
        with open(config.COMPANIES_YAML_PATH, encoding="utf-8") as f:
            companies = yaml.safe_load(f) or []

    for company in companies:
        ats = company.get("ats")
        builder = _ATS_BUILDERS.get(ats)
        if builder is None:
            print(f"WARNING: unknown ats '{ats}' for company '{company.get('name')}', skipping.")
            continue
        scrapers.append(builder(company))

    return scrapers


def load_last_counts() -> dict:
    if not os.path.exists(_LAST_COUNTS_PATH):
        return {}
    with open(_LAST_COUNTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_last_counts(counts: dict) -> None:
    with open(_LAST_COUNTS_PATH, "w", encoding="utf-8") as f:
        json.dump(counts, f, indent=2, sort_keys=True)


def main() -> None:
    scrapers = build_scrapers()
    last_counts = load_last_counts()

    all_postings = []
    current_counts = {}
    for scraper in scrapers:
        source_name = getattr(scraper, "company_name", None) or type(scraper).__name__
        try:
            postings = scraper.get_postings()
        except Exception as e:
            print(f"ERROR: {source_name} failed: {e}", file=sys.stderr)
            continue

        print(f"{source_name}: {len(postings)} posting(s).")
        current_counts[source_name] = len(postings)
        if len(postings) == 0 and last_counts.get(source_name, 0) > 0:
            print(
                f"WARNING: {source_name} previously returned "
                f"{last_counts[source_name]} posting(s), now returns 0 — "
                "possible scraper breakage.",
                file=sys.stderr,
            )
        all_postings.extend(postings)

    save_last_counts(current_counts)

    if not all_postings:
        print("ERROR: No postings fetched from any source.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(all_postings)} total postings across all sources.")

    european_postings = filters.filter_and_tag(all_postings)
    print(f"{len(european_postings)} posting(s) after role/location filtering.")

    seen = load_seen_links(config.CSV_PATH)
    new_postings = [p for p in european_postings if p.link not in seen]

    print(f"{len(new_postings)} new posting(s) since last run.")

    if new_postings:
        append_new_postings(config.CSV_PATH, new_postings)
        print(f"Saved to {config.CSV_PATH}.")
        write_postings_table(config.README_PATH, load_all_postings(config.CSV_PATH))
        print(f"Updated postings table in {config.README_PATH}.")
        send_new_postings(config.DISCORD_WEBHOOK_URL, new_postings)
    else:
        print("No new postings.")


if __name__ == "__main__":
    main()
