# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Scrapes **European** internship postings (Italy first — Milan especially — then EU/EEA/Switzerland) from a company watchlist plus the SimplifyJobs internship GitHub repo, every 6 hours, diffs against a local CSV of known postings, posts new ones to Discord, and regenerates a sectioned postings table in this README. Designed to run on GitHub Actions so it works 24/7 without a laptop.

The UK is deliberately excluded, not just deprioritized: the user is an EU citizen with full EU/EEA/Switzerland work authorization, but the UK requires visa sponsorship post-Brexit.

This repo previously targeted only US internships (NVIDIA + SimplifyJobs). It pivoted to Europe/Milan-first in 2026-09; see git history before that point for the old architecture.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env — copy from .env.example and fill in overrides if needed)
cp .env.example .env
python main.py

# Second run should print "0 new posting(s) since last run." (dedup check)
python main.py
```

## Architecture

- `config.py` — loads env vars (`SIMPLIFY_README_URL`, `CSV_PATH`, `README_PATH`, `COMPANIES_YAML_PATH`, `DISCORD_WEBHOOK_URL`) and the keyword lists used for filtering (`INTERN_KEYWORDS`, `EXCLUDE_KEYWORDS`, `ROLE_KEYWORDS`, `CHEM_BIO_KEYWORDS`) — all keywords live here, not hardcoded in scrapers.
- `scrapers/base.py` — `Posting` dataclass (`company`, `role`, `location`, `link`, `date_added`, `source`, plus `country`, `city`, `category`, `priority`, `ats`, `first_seen`) and the `Scraper` ABC all scrapers implement.
- **ATS scrapers** — one generic, reusable class per Applicant Tracking System, each parameterized by a company slug/tenant read from `companies.yaml` rather than hardcoded per company. Every one is unauthenticated and publicly accessible; no API keys needed:
  - `scrapers/greenhouse.py` — `GET boards-api.greenhouse.io/v1/boards/{slug}/jobs`. Note: this API host is correct even for EU-data-residency tenants whose public careers page is served from `job-boards.eu.greenhouse.io` (e.g. Scalapay) — only the UI domain changes, not the API host.
  - `scrapers/lever.py` — `GET api.lever.co/v0/postings/{slug}?mode=json`. Some companies are hosted on `api.eu.lever.co` instead (EU data residency) — pass `host:` in `companies.yaml` if so; check the company's careers page network requests to tell which.
  - `scrapers/ashby.py` — `GET api.ashbyhq.com/posting-api/job-board/{slug}`.
  - `scrapers/workday.py` — generalized from the old NVIDIA-only scraper. `POST {tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`. `wd_host` (e.g. `wd3`, `wd5`) and `site` are per-tenant path segments that must be read off the company's actual careers URL — they vary company to company and can't be guessed.
  - `scrapers/smartrecruiters.py` — `GET api.smartrecruiters.com/v1/companies/{company_identifier}/postings`. `company_identifier` is case-sensitive and often differs from the display name (Bosch's is `BoschGroup`) — confirm it from the company's real `jobs.smartrecruiters.com/...` URL.
  - `scrapers/personio.py` — `GET {slug}.{host_suffix}/xml` (default host suffix `jobs.personio.de`; some tenants use `.com` instead — check the real careers hostname).
  - `scrapers/workable.py` — `GET apply.workable.com/api/v1/widget/accounts/{slug}`.
  - `scrapers/teamtailor.py` — `GET {slug}.teamtailor.com/jobs.json`, a public per-tenant JSON Feed. Distinct from Teamtailor's official Public API (which needs a per-company API key) — this feed endpoint needs no key.
- `scrapers/simplify_github.py` — fetches raw HTML-flavored markdown from the SimplifyJobs repo README (still US-focused upstream; only its non-US rows survive the location filter below). See inline comments for its HTML-table parsing quirks (unchanged from before the Europe pivot).
- `companies.yaml` — the watchlist. Each entry: `name`, `ats` (one of the types above), the ATS-specific slug/tenant fields, `category` (`big-tech`/`startup`/`pharma-biotech`/`finance`/`consulting`), and `priority` (`high`/`normal`; `high` surfaces first in the README and Discord — used for Milan/Italian/otherwise especially relevant companies). `main.py` builds one scraper instance per entry, dispatched by `ats`.
- `filters.py` — applied to the merged output of every scraper before dedup:
  - `passes_role_filter()` — a title must match one of `config.INTERN_KEYWORDS` (multilingual: stage, tirocinio, praktikum, stagiaire, becario, trainee, etc.), must not match `config.EXCLUDE_KEYWORDS` (senior/staff/new-grad/graduate-program wording), and must match `config.ROLE_KEYWORDS` or `config.CHEM_BIO_KEYWORDS` (the bonus computational-chemistry/drug-discovery/pharma-data interest).
  - `filter_and_tag()` — also normalizes location to `(city, country)` and drops anything that doesn't resolve to EU/EEA/Switzerland/remote-Europe. **UK postings are dropped entirely**, not tagged — the user needs sponsorship there as an EU citizen post-Brexit, unlike the rest of the EU/EEA/Switzerland. UK detection uses the same exclusion path as US detection (`_EXCLUDED_MARKERS` in `filters.py`). Location matching uses whole-word regex matching throughout (`\b`-bounded), not naive substring checks — a naive `"uk" in location.lower()` check will false-positive on city names like "Tukwila" ("T-**uk**-wila"); this bit us once during development, hence the word-boundary requirement everywhere in `filters.py`.
- `notifications/discord.py` — posts newly-found postings to a Discord webhook (`DISCORD_WEBHOOK_URL`; skipped silently if unset), Milan and `priority: high` postings first, batched under Discord's message-length limit.
- `storage/csv_store.py` — persistence layer. `load_seen_links()` returns the set of already-known application URLs for dedup (by `link`). `load_all_postings()` reads the full CSV back into `Posting` objects (used to regenerate the README table with the complete history, not just this run's new postings). `append_new_postings()` appends only new rows and stamps `first_seen` once, at first sighting.
- `storage/readme_table.py` — regenerates the postings table into `README.md`, split into sections (Milan / Rest of Italy / Rest of Europe / Remote (Europe)), newest-first within each, replacing the content between `<!-- POSTINGS_TABLE_START -->` / `<!-- POSTINGS_TABLE_END -->` markers. No pruning/archiving is implemented yet — the README can grow large over time.
- `main.py` — orchestrator: builds the scraper list (SimplifyJobs + one per `companies.yaml` entry) → runs each independently (one failing doesn't kill the run) → merges postings → applies `filters.filter_and_tag()` → diffs against seen links → appends CSV → regenerates README → notifies Discord. Also tracks per-source posting counts in `last_run_counts.json` (committed alongside the CSV) and prints a warning if a source that previously returned postings suddenly returns 0 — a signal a scraper silently broke.
- `.github/workflows/scrape.yml` — runs on a 6-hour cron (`workflow_dispatch` also available for manual runs), passes the `DISCORD_WEBHOOK_URL` repo secret into the run step, commits `internships.csv`/`README.md`/`last_run_counts.json` changes back to the repo.

## Adding a company to the watchlist

1. Visit the company's real careers page and find an actual open posting.
2. Determine its ATS by inspecting the posting URL or the page's network requests — don't assume from the company's size or country. Common tells: `boards.greenhouse.io`/`job-boards.greenhouse.io` (Greenhouse), `jobs.lever.co` (Lever), `jobs.ashbyhq.com` (Ashby), `myworkdayjobs.com` (Workday), `jobs.smartrecruiters.com` (SmartRecruiters), `*.jobs.personio.de`/`.com` (Personio), `apply.workable.com` (Workable), `*.teamtailor.com` (Teamtailor).
3. Extract the slug/tenant from that URL (for Workday, also the `wdN` host and the `site` path segment).
4. Hit the corresponding public API directly (see the scraper docstrings above for the exact URL) to confirm it returns real postings before adding it — don't add an unverified entry.
5. Add an entry to `companies.yaml` with `name`, `ats`, the slug/tenant fields, `category`, and `priority`.
6. Run `python main.py` and confirm the new company's count appears in the per-source log line.

## Updating the target internship year

`SIMPLIFY_README_URL` currently defaults (in `config.py`) to the `Summer2027-Internships` repo. When SimplifyJobs creates the `Summer2028-Internships` repo, update the default in `config.py` and/or `SIMPLIFY_README_URL` in `.env` (local) and the commented example in `scrape.yml`. The URL pattern is:
```
https://raw.githubusercontent.com/SimplifyJobs/Summer20XX-Internships/dev/README.md
```

## GitHub Actions setup

Requires one repository secret: `DISCORD_WEBHOOK_URL` (create a webhook in the target Discord channel's Integrations settings, then add it under Settings → Secrets and variables → Actions in the GitHub repo). Without it, the workflow still runs fine — the Discord step is skipped, only the CSV/README are updated. The workflow also needs its default `GITHUB_TOKEN` (already covered by the `permissions: contents: write` block) to commit changes back to the repo.

## Known gaps (Phase 2, not yet built)

- Only ~11 watchlist companies so far (small verified seed) — see `companies.yaml` for the plan to grow toward 30-50.
- No aggregator APIs (Adzuna, Arbeitnow, etc.) yet — watchlist + SimplifyJobs only.
- No relevance scoring beyond the `priority`/Milan-first sort — no chemistry/bio-relevance weighting yet.
- No pruning/archiving of old postings from the README.
