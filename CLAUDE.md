# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Scrapes internship postings from multiple sources (currently the [SimplifyJobs](https://github.com/SimplifyJobs) internship GitHub repo and NVIDIA's careers site) every 6 hours, diffs against a local CSV of known postings, and regenerates a postings table in this README. Designed to run on GitHub Actions so it works 24/7 without a laptop.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env — copy from .env.example and fill in overrides if needed)
cp .env.example .env
python main.py

# Second run should print "0 new posting(s) since last run." / "No new postings." (dedup check)
python main.py
```

## Architecture

- `config.py` — loads env vars; `SIMPLIFY_README_URL`, `CSV_PATH`, `README_PATH`.
- `scrapers/base.py` — `Posting` dataclass (`company`, `role`, `location`, `link`, `date_added`, `source`) and the `Scraper` ABC all scrapers implement.
- `scrapers/simplify_github.py` — fetches raw HTML-flavored markdown from the SimplifyJobs repo README. **The README is an HTML `<table>` (`<tr><td>...`), not a markdown pipe-table** — this changed at some point and the old pipe-row regex parser silently returned 0 postings against it. The parser now extracts `<tr>`/`<td>` blocks directly. Skips sub-role rows (company cell is just `↳`). Handles multi-location cells, including the `<details><summary>N locations</summary>...</details>` collapsed form. `date_added` here is a **relative age string** sourced from Simplify's "Age" column (e.g. `"3d"`), not an absolute date — don't assume it's parseable as a date. Closed (🔒) postings are already excluded from the main table upstream, so no locked-row filtering is needed.
- `scrapers/nvidia_careers.py` — hits NVIDIA's Workday CxS JSON endpoint (`POST nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs`), unauthenticated and structured, no HTML scraping needed. Paginates by `offset`/`limit` up to a cap. Filters client-side to titles containing "intern", excluding new-grad postings, matching one of README.md's target keywords (software engineer, data science, data analyst, data engineer, ml engineer, ai engineer), and containing "2027" (Workday's full-text search is loose and returns off-target results otherwise). **As of this writing NVIDIA has no live Summer 2027 SWE/DS internships posted** (their current listings are "Fall 2026") — 0 results from this scraper right now is expected, not a bug; it'll start returning postings once NVIDIA opens that cycle.
  - **Google, Apple, Meta careers sites were evaluated and skipped.** Google's Jobs API was shut down in 2021 and no public JSON endpoint was found. Apple's `jobs.apple.com` API requires session/CSRF setup obtained from the rendered page (`"User Unauthorized"` without it). Meta's `metacareers.com` is backed by an internal GraphQL endpoint with a `doc_id` hash that rotates on deploy. All three would need a headless browser or reverse-engineered auth flows likely to break silently — deliberately not built. Revisiting them is a separate future task.
- `storage/csv_store.py` — persistence layer. `load_seen_links()` returns the set of already-known application URLs for dedup. `load_all_postings()` reads the full CSV back into `Posting` objects (used to regenerate the README table with the complete history, not just this run's new postings). `append_new_postings()` appends only new rows, including a `source` column.
- `storage/readme_table.py` — regenerates a markdown table of all known postings (newest-found first) into `README.md`, replacing the content between `<!-- POSTINGS_TABLE_START -->` / `<!-- POSTINGS_TABLE_END -->` markers (added automatically on first run if absent). This can make the README grow large over time as postings accumulate — no pruning/archiving is implemented yet.
- `main.py` — orchestrator: run each scraper independently (one failing doesn't kill the run), merge postings → diff against seen links → append CSV → regenerate README table.
- `.github/workflows/scrape.yml` — runs on a 6-hour cron (`workflow_dispatch` also available for manual runs), commits any `internships.csv`/`README.md` changes back to the repo.

There is no email/notification step — email support (Gmail SMTP) was removed; postings are surfaced only via the README table.

## Updating the target internship year

`SIMPLIFY_README_URL` currently defaults (in `config.py`) to the `Summer2027-Internships` repo. When SimplifyJobs creates the `Summer2028-Internships` repo, update the default in `config.py` and/or `SIMPLIFY_README_URL` in `.env` (local) and the commented example in `scrape.yml`. The URL pattern is:
```
https://raw.githubusercontent.com/SimplifyJobs/Summer20XX-Internships/dev/README.md
```

## GitHub Actions setup

No repository secrets are required — the workflow only needs its default `GITHUB_TOKEN` (already covered by the `permissions: contents: write` block) to commit `internships.csv`/`README.md` back to the repo.
