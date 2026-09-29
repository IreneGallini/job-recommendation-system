## Done (2026-09-29)
- Complete collection: every internship in the 14 eligible countries (site "All" tab)
- Inbox: unread target-role postings, ranked; Applied / Ineligible / Not interested / Read (site "Inbox" tab)
- Recommendation score (Milan/Turin area, summer fit, MS/PhD penalty, recency) — weights in `config.SCORE_WEIGHTS`
- Posted date, duration / start / summer_fit parsing, degree requirement parsing
- Links open in a new tab (site)
- Watchlist grown to 31 companies (Italy + big tech); Google / Microsoft / Apple / Meta tracked manually in `outreach.yaml`
- Outreach tab + `outreach.yaml`

## Still to do
- Outreach plan (written doc)
- One-time: enable GitHub Pages (Settings → Pages → main, /docs) — repo must be public on a free plan
- Add named contacts to `outreach.yaml` as you find them
- More companies: Bending Spoons, Reply, Stellantis, Intesa Sanpaolo, Pirelli, Leonardo aren't on a supported ATS (or weren't found) — custom scrapers or manual checks

## Duration and timing (important) — implemented in enrich.py
I'm only available mid-May to early September (about 14-16 weeks), so fixed
6-month internships usually won't work.
- Parse duration and start date from the title/description when present, in
  English and Italian (e.g. "3 months", "12 weeks", "6 mesi", "durata: 6 mesi",
  "start: September", "inizio: settembre", "summer internship",
  "stage estivo").
- Add `duration_months`, `start_hint`, and `summer_fit` (yes / no / unknown)
  to the Posting model and CSV.
- summer_fit = yes if it's explicitly a summer program or duration <= 4
  months starting May-June; no if it's clearly >= 5 months or starts
  Sept-March; otherwise unknown.
- Never drop "unknown" postings, but sort "yes" first, then "unknown", and
  put "no" in a collapsed section of the README. Discord notifications should
  only include "yes" and "unknown", and should label which one.
- Add a config flag in `companies.yaml` for companies known to run structured
  summer programs so they're boosted in ranking.
