# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Scrapes **European** internship postings (Italy first — Milan especially — then an allowlist of 13 other countries: Switzerland, France, Germany, Denmark, Norway, Sweden, Finland, Spain, Portugal, Netherlands, Belgium, Austria, Ireland) from a company watchlist plus the SimplifyJobs internship GitHub repo, every 6 hours, diffs against a local CSV of known postings, posts new ones to Discord, and regenerates a sectioned postings table in this README. Designed to run on GitHub Actions so it works 24/7 without a laptop.

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

# Parser/ranking tests
python -m pytest tests

# Preview the site
python -m http.server -d docs   # then open http://localhost:8000
```

## Architecture

- `config.py` — loads env vars (`SIMPLIFY_README_URL`, `CSV_PATH`, `README_PATH`, `COMPANIES_YAML_PATH`, `OUTREACH_YAML_PATH`, `DOCS_DIR`, `SITE_URL`, `DISCORD_WEBHOOK_URL`), the keyword lists used for filtering (`INTERN_KEYWORDS`, `EXCLUDE_KEYWORDS`, `ROLE_KEYWORDS`, `CHEM_BIO_KEYWORDS`), the preferred commuting areas (`MILAN_AREA_CITIES`, `TURIN_AREA_CITIES`) and the recommendation weights (`SCORE_WEIGHTS`, `RECENCY_DAYS`) — all tunables live here, not hardcoded in scrapers.
- `scrapers/base.py` — `Posting` dataclass (`company`, `role`, `location`, `link`, `date_added`, `source`, `country`, `city`, `category`, `priority`, `ats`, `first_seen`, plus `posted_date`, `last_seen`, `role_match`, `summer_program`, `duration_months`, `start_hint`, `summer_fit`, `degree_req`, `described`, and the in-memory-only `description`) and the `Scraper` ABC. `Scraper.fetch_description()` is optional: scrapers whose list endpoint already includes descriptions (Lever, Ashby, Workable with `details=true`, Teamtailor, Personio, Amazon) set `description` directly; Greenhouse, SmartRecruiters and Workday fetch it per posting, only for new postings that passed filtering.
- **ATS scrapers** — one generic, reusable class per Applicant Tracking System, each parameterized by a company slug/tenant read from `companies.yaml` rather than hardcoded per company. Every one is unauthenticated and publicly accessible; no API keys needed:
  - `scrapers/greenhouse.py` — `GET boards-api.greenhouse.io/v1/boards/{slug}/jobs`. Note: this API host is correct even for EU-data-residency tenants whose public careers page is served from `job-boards.eu.greenhouse.io` (e.g. Scalapay) — only the UI domain changes, not the API host.
  - `scrapers/lever.py` — `GET api.lever.co/v0/postings/{slug}?mode=json`. Some companies are hosted on `api.eu.lever.co` instead (EU data residency) — pass `host:` in `companies.yaml` if so; check the company's careers page network requests to tell which.
  - `scrapers/ashby.py` — `GET api.ashbyhq.com/posting-api/job-board/{slug}`.
  - `scrapers/workday.py` — generalized from the old NVIDIA-only scraper. `POST {tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`. `wd_host` (e.g. `wd3`, `wd5`) and `site` are per-tenant path segments that must be read off the company's actual careers URL — they vary company to company and can't be guessed. `search_text` may be a list; big global tenants use `["intern Italy", "intern"]` because a bare "intern" search hits the 200-result cap on US postings first (Workday's full-text search matches location names). When `locationsText` is missing or just "2 Locations", the location is read from the job URL path. Requests go through a retrying session — Workday resets connections when several tenants on one `wdN` host are hit concurrently.
  - `scrapers/smartrecruiters.py` — `GET api.smartrecruiters.com/v1/companies/{company_identifier}/postings`. `company_identifier` is case-sensitive and often differs from the display name (Bosch's is `BoschGroup`) — confirm it from the company's real `jobs.smartrecruiters.com/...` URL.
  - `scrapers/personio.py` — `GET {slug}.{host_suffix}/xml` (default host suffix `jobs.personio.de`; some tenants use `.com` instead — check the real careers hostname).
  - `scrapers/workable.py` — `GET apply.workable.com/api/v1/widget/accounts/{slug}`.
  - `scrapers/teamtailor.py` — `GET {slug}.teamtailor.com/jobs.json`, a public per-tenant JSON Feed. Distinct from Teamtailor's official Public API (which needs a per-company API key) — this feed endpoint needs no key.
- `scrapers/amazon.py` — Amazon runs its own careers system, so it has a dedicated scraper: `GET amazon.jobs/en/search.json?base_query=intern&country={ISO3}`, one search per eligible country. `ats: amazon` in `companies.yaml`. Google, Microsoft, Apple and Meta have no verified public jobs API and are tracked manually in `outreach.yaml` instead.
- `scrapers/simplify_github.py` — fetches raw HTML-flavored markdown from the SimplifyJobs repo README (still US-focused upstream; only its non-US rows survive the location filter below). See inline comments for its HTML-table parsing quirks (unchanged from before the Europe pivot).
- `companies.yaml` — the watchlist. Each entry: `name`, `ats` (one of the types above), the ATS-specific slug/tenant fields, `category` (`big-tech`/`startup`/`pharma-biotech`/`finance`/`consulting`), `priority` (`high`/`normal`; adds to the recommendation score — used for Milan/Italian/otherwise especially relevant companies), and optional `summer_program: true` for companies known to run structured summer programs (ranking boost). `main.py` builds one scraper instance per entry, dispatched by `ats`.
- `outreach.yaml` — companies/people to contact, rendered on the site's Outreach tab with each company's open postings attached (matched by company name). Seeded at company level with LinkedIn people-search links; named contacts are added by hand.
- `filters.py` — applied to the merged output of every scraper before dedup:
  - `is_internship()` — a title must match one of `config.INTERN_KEYWORDS` (multilingual: stage, tirocinio, praktikum, stagiaire, becario, trainee, etc.) and must not match `config.EXCLUDE_KEYWORDS` (senior/staff/new-grad/graduate-program wording). "intern" and "stage" must be standalone words ("International", "Internal", "multi-stage" don't count); the rest match as substrings so German compounds like "Pflichtpraktikum" hit.
  - `matches_target_role()` — `config.ROLE_KEYWORDS` or `config.CHEM_BIO_KEYWORDS` (the bonus computational-chemistry/drug-discovery/pharma-data interest). Non-matching internships are **kept** with `role_match=False` (they feed the site's "All" tab); the README, Discord and the Inbox show only `role_match=True`.
  - `filter_and_tag()` — keeps every internship in an eligible location, normalizes location to `(city, country)` and the raw ATS date to `posted_date` (`dates.py`), and drops anything that doesn't resolve to an allowlisted country (`_EUROPE_COUNTRIES` in `filters.py` — deliberately not the full EU/EEA; e.g. Romania, Poland are excluded) or remote-Europe. **UK postings are dropped entirely**, not tagged — the user needs sponsorship there as an EU citizen post-Brexit, unlike the rest of the EU/EEA/Switzerland. UK detection uses the same exclusion path as US detection (`_EXCLUDED_MARKERS` in `filters.py`). Location matching uses whole-word regex matching throughout (`\b`-bounded), not naive substring checks — a naive `"uk" in location.lower()` check will false-positive on city names like "Tukwila" ("T-**uk**-wila"); this bit us once during development, hence the word-boundary requirement everywhere in `filters.py`. A `_CITIES` map resolves city-only strings ("Milano", "Zürich"); because many European city names also exist in the US (Dublin OH, Vienna VA, Paris TX), a bare city match is rejected when the location also names a US state. Multi-location postings resolve to their most preferred location (Milan > Turin > rest of Italy > rest of Europe > remote-Europe).
- `enrich.py` — parses title + description (EN/IT, some DE/FR/ES) into `duration_months`, `start_hint` (`summer` or a month like `sep`), `summer_fit` (`yes`: explicit summer program or ≤4 months starting May–June; `no`: ≥5 months or starts Sept–March; else `unknown` — never dropped) and `degree_req` (`phd`/`masters`/`any`/`unknown`; a Bachelor's mention means `any`). The user is available mid-May to early September only.
- `ranking.py` — `score()` (region, summer fit, summer program, priority, role match, chem/bio, degree penalty, recency) using `config.SCORE_WEIGHTS`; `rank()` is the single ordering used by the README, Discord and the site. `active()` = postings whose `last_seen` is within 3 days of the newest run (closed postings drop out of the README/Inbox).
- `notifications/discord.py` — posts new target-role postings with `summer_fit` yes/unknown (labelled `[summer ✓]` / `[summer ?]`) to a Discord webhook (`DISCORD_WEBHOOK_URL`; skipped silently if unset), in `ranking.rank()` order, batched under Discord's message-length limit.
- `storage/csv_store.py` — persistence layer. `load_all_postings()` reads the full CSV back into `Posting` objects (tolerant of older headers). `save_all_postings()` rewrites the whole file every run (not append-only) so `last_seen` stays current; `csv_needs_migration()` detects an older header, in which case every stored row is re-enriched once. Dedup is by `link`.
- `storage/readme_table.py` — regenerates the postings table into `README.md`: active target-role postings only, sectioned (Milan area / Turin area / Rest of Italy / Rest of Europe / Remote (Europe)), ranked by score within each, `summer_fit=no` in a collapsed `<details>` block, replacing the content between `<!-- POSTINGS_TABLE_START -->` / `<!-- POSTINGS_TABLE_END -->` markers.
- `storage/site_data.py` + `docs/` — the GitHub Pages site. `docs/index.html`, `app.js`, `style.css` are hand-written and committed; `site_data.py` regenerates `docs/postings.json` (every stored posting with score/region/active) and `docs/outreach.json` each run. Tabs: **Inbox** (unread active target-role postings, ranked, with Applied / Ineligible / Not interested / Read actions), **All** (every eligible internship, filterable), **Outreach**. Triage and outreach status live in the browser's localStorage, with Export/Import JSON to move them between devices — nothing the user does on the site is written back to the repo. Test locally with `python -m http.server -d docs`.
- `main.py` — orchestrator: builds the scraper list (SimplifyJobs + one per `companies.yaml` entry) → runs them concurrently (one failing doesn't kill the run) → merges postings → applies `filters.filter_and_tag()` → merges with the stored CSV (new postings get `first_seen`; existing ones get refreshed location/role fields and `last_seen`) → fetches descriptions (parallel, capped at 500/run; failed fetches keep `described=false` and are retried next run) and runs `enrich.enrich()` → saves the CSV → regenerates README and site data → notifies Discord. Also tracks per-source posting counts in `last_run_counts.json` (committed alongside the CSV) and prints a warning if a source that previously returned postings suddenly returns 0 — a signal a scraper silently broke.
- `.github/workflows/scrape.yml` — runs on a 6-hour cron (`workflow_dispatch` also available for manual runs), passes the `DISCORD_WEBHOOK_URL` repo secret into the run step, commits `internships.csv`/`README.md`/`last_run_counts.json`/`docs/` changes back to the repo.

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

The site needs a one-time manual setting: Settings → Pages → Deploy from a branch → `main`, folder `/docs`. On a free GitHub plan the repo must be public for Pages. `SITE_URL` in `config.py` (linked from the README) defaults to `https://irenegallini.github.io/job-recommendation-system/`.

## Known gaps (Phase 2, not yet built)

- 31 watchlist companies. Several relevant Milan/Turin employers (Bending Spoons, Reply, Stellantis, Intesa Sanpaolo, Pirelli, Leonardo) aren't on a supported ATS or weren't found — listed in `outreach.yaml` for manual checking.
- No aggregator APIs (Adzuna, Arbeitnow, etc.) yet — watchlist + SimplifyJobs only.
- The CSV keeps closed postings forever (they're only hidden via `ranking.active()`); no archiving yet.
- Site triage state is per-browser (localStorage + manual Export/Import), not synced.
