# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Scrapes the [SimplifyJobs](https://github.com/SimplifyJobs) internship GitHub repo every hour, diffs against a local CSV of known postings, and emails a digest of new entries. Designed to run on GitHub Actions so it works 24/7 without a laptop.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires .env — copy from .env.example and fill in credentials)
cp .env.example .env
python main.py

# Second run should print "No new postings. No email sent." (dedup check)
python main.py
```

## Architecture

- `config.py` — loads env vars; `EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD`, `SIMPLIFY_README_URL`, `CSV_PATH`
- `scrapers/simplify_github.py` — fetches raw markdown from the SimplifyJobs repo, regex-parses the markdown table into `Posting` dataclasses. Skips locked (`🔒`) rows and `↳` sub-role rows.
- `storage/csv_store.py` — persistence layer. `load_seen_links()` returns the set of already-known application URLs; `append_new_postings()` appends only new rows. The CSV is committed back to the repo by the GitHub Actions workflow after each run.
- `notifiers/email_notifier.py` — sends a single HTML digest email via Gmail SMTP (App Password). Only called when there are new postings.
- `main.py` — orchestrator: scrape → diff against seen links → append CSV → send email.
- `.github/workflows/scrape.yml` — runs on a 1-hour cron, commits any CSV changes back to the repo.

## Updating the target internship year

When SimplifyJobs creates the `Summer2027-Internships` repo, update `SIMPLIFY_README_URL` in `.env` (local) and in the `scrape.yml` env comment (GitHub Actions). The URL pattern is:
```
https://raw.githubusercontent.com/SimplifyJobs/Summer20XX-Internships/dev/README.md
```

## GitHub Actions setup

Add two repository secrets (`Settings → Secrets → Actions`):
- `EMAIL_ADDRESS` — your Gmail address
- `EMAIL_APP_PASSWORD` — Gmail App Password (generate at myaccount.google.com/apppasswords; requires 2FA)
