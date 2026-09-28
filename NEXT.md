- outreach plan 
- list active companies in italy
- pay special attention to big tech
- data posted
- scraper collects everything possible -> in one page (Complete collection)
- current page: ranked by reccomandation + latest date
    - add feature to easily eliminate ineligible, already applied etc. Stack like
- implement reccomandation component based on my preferences (may-september, milan/turin area)
- qualifications (rank lower if it says requires MS/Phd)
- from readme open link in other page


## Duration and timing (important)
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