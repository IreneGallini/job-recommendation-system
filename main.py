import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import yaml

import config
import enrich
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
from scrapers.amazon import AmazonScraper
from storage.csv_store import csv_needs_migration, load_all_postings, save_all_postings, today
from storage.readme_table import write_postings_table
from storage.site_data import write_site_data

_LAST_COUNTS_PATH = "last_run_counts.json"
_MAX_DESCRIPTION_FETCHES = 500

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
    "amazon": lambda c: AmazonScraper(
        c["name"], c["category"], c["priority"], search_text=c.get("search_text", "intern")
    ),
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
        scraper = builder(company)
        scraper.summer_program = bool(company.get("summer_program", False))
        scrapers.append(scraper)

    return scrapers


def _source_name(scraper) -> str:
    return getattr(scraper, "company_name", None) or type(scraper).__name__


def _scrape(scraper):
    """Run one scraper; None on failure (one failing source doesn't kill the run)."""
    started = time.monotonic()
    try:
        postings = scraper.get_postings()
    except Exception as e:
        print(f"ERROR: {_source_name(scraper)} failed after {time.monotonic() - started:.0f}s: {e}", file=sys.stderr)
        return None
    scraper.elapsed = time.monotonic() - started
    return postings


def _describe(p, scraper) -> None:
    """Fill p.description via the source's detail endpoint if the list
    response didn't include it. Sets p.described only on success."""
    if p.description or scraper is None:
        p.described = True
        return
    try:
        p.description = scraper.fetch_description(p)
        p.described = True
    except Exception as e:
        print(f"WARNING: description fetch failed for {p.link}: {e}", file=sys.stderr)


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
    scraper_for_link = {}
    current_counts = {}
    # Sources are independent network calls; fetch them concurrently, then
    # process results in watchlist order so the log stays readable.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_scrape, scrapers))
    for scraper, postings in zip(scrapers, results):
        source_name = _source_name(scraper)
        if postings is None:
            continue

        for p in postings:
            p.summer_program = getattr(scraper, "summer_program", False)
            scraper_for_link[p.link] = scraper
        print(f"{source_name}: {len(postings)} posting(s) ({scraper.elapsed:.0f}s).")
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

    eligible = list({p.link: p for p in filters.filter_and_tag(all_postings)}.values())
    print(
        f"{len(eligible)} internship(s) in eligible locations "
        f"({sum(p.role_match for p in eligible)} in target roles)."
    )

    migrating = csv_needs_migration(config.CSV_PATH)
    stored = {p.link: p for p in load_all_postings(config.CSV_PATH)}
    run_date = today()
    new_postings = []
    to_enrich = []
    for p in eligible:
        existing = stored.get(p.link)
        if existing is None:
            p.first_seen = run_date
            p.last_seen = run_date
            stored[p.link] = p
            new_postings.append(p)
            to_enrich.append(p)
            continue
        # Refresh what the source may have changed (or what an older parser
        # got wrong), keep first_seen and the parsed enrichment fields.
        existing.role = p.role
        existing.location, existing.city, existing.country = p.location, p.city, p.country
        existing.role_match = p.role_match
        existing.summer_program = p.summer_program
        existing.posted_date = p.posted_date or existing.posted_date
        existing.last_seen = run_date
        if migrating or not existing.described:
            # Rows written before enrichment existed, or whose description
            # fetch failed last time, get (re)parsed.
            existing.description = p.description
            to_enrich.append(existing)

    print(f"{len(new_postings)} new posting(s) since last run.")

    # New postings first, then retries, capped so a flaky source can't make
    # every run re-fetch hundreds of descriptions.
    to_enrich = to_enrich[:_MAX_DESCRIPTION_FETCHES]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda p: _describe(p, scraper_for_link.get(p.link)), to_enrich))
    for p in to_enrich:
        enrich.enrich(p)
    failed = sum(not p.described for p in to_enrich)
    print(f"Enriched {len(to_enrich)} posting(s) ({failed} description fetch(es) failed, will retry).")

    all_stored = list(stored.values())
    save_all_postings(config.CSV_PATH, all_stored)
    write_postings_table(config.README_PATH, all_stored)
    write_site_data(config.DOCS_DIR, all_stored, config.OUTREACH_YAML_PATH)
    print(
        f"Saved {len(all_stored)} posting(s) to {config.CSV_PATH}; "
        f"updated {config.README_PATH} and {config.DOCS_DIR}/."
    )


if __name__ == "__main__":
    main()
