"""Find which supported ATS a company uses and propose companies.yaml entries.

Offline helper, not part of the scheduled run. Writes candidates.yaml for
review; never edits companies.yaml (entries there must be verified by hand,
see CLAUDE.md).

Seeds (merged, deduplicated by normalized name, watchlist companies skipped):
  - employers in internships.csv that aren't on the watchlist (Adzuna and
    SimplifyJobs rows): companies known to post internships
  - Wikidata: companies in the chosen countries with an official website and
    >=200 employees, a stock listing, or a reported revenue
  - --names FILE: one company name per line (optionally "name, website")

Detection, per company:
  1. posting link: a stored posting's link already points at an ATS
  2. website scan: homepage + careers pages, regex for ATS URLs (the only way
     to find Workday tenants, whose wd host and site can't be guessed)
  3. slug probe: guess slugs from the name and try each ATS's public API
Every candidate is then verified by running the real scraper: it must return
>0 postings. Results are cached in .cache/discover_ats.json.

Usage:
  python tools/discover_ats.py [--limit N] [--countries it,ch] [--no-wikidata]
                               [--names FILE] [--refresh]
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlsplit

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import filters  # noqa: E402
import main  # noqa: E402

_CACHE_PATH = ".cache/discover_ats.json"
_OUTPUT_PATH = "candidates.yaml"
_USER_AGENT = "internship-scraper/1.0 (https://github.com/IreneGallini/job-recommendation-system)"
_TIMEOUT = 12

_WIKIDATA_COUNTRIES = {
    "it": "Q38", "ch": "Q39", "fr": "Q142", "de": "Q183", "dk": "Q35",
    "no": "Q20", "se": "Q34", "fi": "Q33", "es": "Q29", "pt": "Q45",
    "nl": "Q55", "be": "Q31", "at": "Q40", "ie": "Q27",
}
# Separate small queries: one combined UNION times out on the public endpoint.
_WIKIDATA_CRITERIA = (
    "?item wdt:P1128 ?emp . FILTER(?emp >= 200)",  # employees
    "?item wdt:P414 ?x .",  # stock exchange listing
    "?item wdt:P2139 ?x .",  # revenue
)

# ATS URL patterns -> companies.yaml fields. Order matters only for display.
_ATS_PATTERNS = (
    ("greenhouse", re.compile(
        r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)"),
     lambda m: {"slug": m.group(1)}),
    ("lever", re.compile(r"jobs\.(eu\.)?lever\.co/([A-Za-z0-9_.-]+)"),
     lambda m: {"slug": m.group(2), **({"host": "api.eu.lever.co"} if m.group(1) else {})}),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)"),
     lambda m: {"slug": m.group(1)}),
    ("workday", re.compile(
        r"([A-Za-z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"),
     lambda m: {"tenant": m.group(1), "wd_host": m.group(2), "site": m.group(3)}),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)"),
     lambda m: {"company_identifier": m.group(1)}),
    ("personio", re.compile(r"([A-Za-z0-9-]+)\.jobs\.personio\.(de|com)"),
     lambda m: {"slug": m.group(1), **({"host_suffix": "jobs.personio.com"} if m.group(2) == "com" else {})}),
    ("workable", re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)"),
     lambda m: {"slug": m.group(1)}),
    ("teamtailor", re.compile(r"([A-Za-z0-9-]+)\.teamtailor\.com"),
     lambda m: {"slug": m.group(1)}),
)
# Path segments the patterns above can catch that are never a tenant.
_NOT_A_SLUG = {"embed", "api", "v0", "v1", "j", "jobs", "js", "wday", "www", "app", "career", "careers", "static", "assets"}

# ATSs we can't scrape yet: reported so you know a custom scraper would be
# needed (common among big Italian employers).
_UNSUPPORTED_ATS = {
    "SAP SuccessFactors": re.compile(r"successfactors\.(?:com|eu)|jobs\.sap\.com|career\d*\.successfactors", re.I),
    "Oracle Taleo": re.compile(r"taleo\.net", re.I),
    "Oracle Recruiting Cloud": re.compile(r"oraclecloud\.com/hcmUI/CandidateExperience", re.I),
    "iCIMS": re.compile(r"\.icims\.com", re.I),
    "inRecruiting (Zucchetti)": re.compile(r"inrecruiting\.com|intervieweb\.it", re.I),
    "Altamira": re.compile(r"altamiraweb\.net|altamirahrm", re.I),
    "Cornerstone": re.compile(r"csod\.com", re.I),
    "Phenom": re.compile(r"phenompeople\.com", re.I),
    "Eightfold": re.compile(r"eightfold\.ai", re.I),
    "Avature": re.compile(r"avature\.net", re.I),
}

_CAREERS_PATHS = ("/careers", "/jobs", "/lavora-con-noi", "/carriere", "/en/careers", "/it/lavora-con-noi")
_CAREERS_LINK = re.compile(
    r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.{0,200}?)</a>", re.I | re.S)
_CAREERS_WORDS = re.compile(
    r"career|jobs?\b|lavora|carrier|work[ -]with[ -]us|join[ -]us|opportunit|talent|stellen|emploi|empleo", re.I)

# Slug-probed ATSs. Personio is left out: an unknown Personio subdomain
# redirects to personio.com, which rate-limits (429) after a few probes.
_PROBE_ATS = ("greenhouse", "lever", "lever-eu", "ashby", "workable", "smartrecruiters", "teamtailor")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT
    return session


# --- seeds -------------------------------------------------------------------

def seeds_from_csv(watchlist: set[str]) -> list[dict]:
    if not os.path.exists(config.CSV_PATH):
        return []
    seeds = {}
    with open(config.CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = filters.normalize_company(row.get("company", ""))
            if not key or key in watchlist or key == "unknown":
                continue
            seed = seeds.setdefault(key, {"name": row["company"], "website": "", "links": [], "seed": row.get("source", "")})
            seed["links"].append(row.get("link", ""))
    return list(seeds.values())


def seeds_from_wikidata(countries: list[str]) -> list[dict]:
    seeds = {}
    session = _session()
    for code in countries:
        qid = _WIKIDATA_COUNTRIES[code]
        for criterion in _WIKIDATA_CRITERIA:
            query = f"""SELECT ?item ?itemLabel (SAMPLE(?site) AS ?website) WHERE {{
  {{ ?item wdt:P17 wd:{qid} }} UNION {{ ?item wdt:P159/wdt:P17 wd:{qid} }}
  ?item wdt:P856 ?site . {criterion}
  FILTER NOT EXISTS {{ ?item wdt:P576 ?dissolved }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,{code}". }}
}} GROUP BY ?item ?itemLabel"""
            try:
                response = session.get(
                    "https://query.wikidata.org/sparql",
                    params={"query": query, "format": "json"}, timeout=90,
                )
                response.raise_for_status()
            except requests.RequestException as e:
                print(f"WARNING: Wikidata query failed ({code}): {e}", file=sys.stderr)
                continue
            for b in response.json()["results"]["bindings"]:
                name = b["itemLabel"]["value"]
                if re.fullmatch(r"Q\d+", name):  # no label in en/local language
                    continue
                seeds.setdefault(b["item"]["value"], {
                    "name": name, "website": b["website"]["value"], "links": [], "seed": f"wikidata-{code}",
                })
    return list(seeds.values())


def seeds_from_file(path: str) -> list[dict]:
    seeds = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, website = (part.strip() for part in line.partition(","))
            seeds.append({"name": name, "website": website, "links": [], "seed": "names-file"})
    return seeds


# --- detection ---------------------------------------------------------------

def ats_hits(text: str) -> list[tuple[str, dict]]:
    hits = []
    for ats, pattern, fields_of in _ATS_PATTERNS:
        for match in pattern.finditer(text):
            fields = fields_of(match)
            if any(v.lower() in _NOT_A_SLUG for k, v in fields.items() if k in ("slug", "tenant", "company_identifier", "site")):
                continue
            if (ats, fields) not in hits:
                hits.append((ats, fields))
    return hits


def unsupported_hits(text: str) -> list[str]:
    return [name for name, pattern in _UNSUPPORTED_ATS.items() if pattern.search(text)]


_MAX_PAGE_BYTES = 2_000_000
_PAGE_DEADLINE = 15  # seconds per page, total


def fetch_page(session: requests.Session, url: str) -> tuple[str, str] | None:
    """GET an HTML page with a wall-clock deadline and size cap: requests'
    timeout is per socket read, so a server trickling bytes (some bot
    protections do) would otherwise stall a worker for minutes."""
    started = time.monotonic()
    try:
        with session.get(url, timeout=_TIMEOUT, allow_redirects=True, stream=True) as response:
            if response.status_code >= 400 or "html" not in response.headers.get("content-type", ""):
                return None
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                chunks.append(chunk)
                size += len(chunk)
                if size > _MAX_PAGE_BYTES or time.monotonic() - started > _PAGE_DEADLINE:
                    break
            return response.url, b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    except requests.RequestException:
        return None


def scan_website(session: requests.Session, website: str) -> tuple[list, list[str]]:
    """Fetch the homepage and up to 4 careers-looking pages; return
    (supported ATS hits, unsupported ATS names)."""
    pages, texts = [website], []
    base = f"{urlsplit(website).scheme}://{urlsplit(website).netloc}"
    pages += [base + path for path in _CAREERS_PATHS]
    fetched = 0
    seen = set()
    while pages and fetched < 6:
        url = pages.pop(0)
        if url in seen:
            continue
        seen.add(url)
        fetched += 1
        page = fetch_page(session, url)
        if page is None:
            continue
        final_url, html = page
        # The redirect target itself may be the ATS (e.g. /careers -> Workday).
        texts.append(final_url)
        texts.append(html)
        if url == website:
            links = [
                urljoin(final_url, href)
                for href, label in _CAREERS_LINK.findall(html)
                if _CAREERS_WORDS.search(href) or _CAREERS_WORDS.search(re.sub(r"<[^>]+>", " ", label))
            ]
            # Followed links go ahead of the guessed paths.
            pages = [link for link in dict.fromkeys(links) if link.startswith("http")][:3] + pages
    text = "\n".join(texts)
    return ats_hits(text), unsupported_hits(text)


def slug_variants(name: str) -> list[str]:
    words = re.sub(r"[^a-z0-9\s-]", "", filters.normalize_company(name)).split()
    if not words:
        return []
    return list(dict.fromkeys(["".join(words), "-".join(words)]))


def probe_candidates(name: str) -> list[tuple[str, dict]]:
    out = []
    for slug in slug_variants(name):
        for ats in _PROBE_ATS:
            if ats == "lever-eu":
                out.append(("lever", {"slug": slug, "host": "api.eu.lever.co"}))
            elif ats == "smartrecruiters":
                # Identifiers are case-sensitive; CamelCase is the usual form.
                out.append((ats, {"company_identifier": "".join(w.capitalize() for w in slug.split("-"))}))
            else:
                out.append((ats, {"slug": slug}))
    return list({json.dumps(c, sort_keys=True): c for c in out}.values())


def verify(name: str, ats: str, fields: dict) -> dict | None:
    """Run the real scraper; None unless it returns postings."""
    entry = {"name": name, "ats": ats, **fields, "category": "TODO", "priority": "normal"}
    try:
        postings = main._ATS_BUILDERS[ats](entry).get_postings()
    except Exception:
        return None
    if not postings:
        return None
    europe = filters.filter_and_tag(postings)
    sample = (europe or postings)[0]
    return {
        "entry": entry,
        "jobs": len(postings),
        "europe_jobs": sum(filters.normalize_location_text(p.location) is not None for p in postings),
        "europe_internships": len(europe),
        "target_role_internships": sum(p.role_match for p in europe),
        "sample": f"{sample.role} — {sample.location}",
    }


def greenhouse_board_name(session: requests.Session, slug: str) -> str:
    try:
        response = session.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}", timeout=_TIMEOUT)
        return response.json().get("name", "") if response.ok else ""
    except (requests.RequestException, ValueError):
        return ""


def discover(seed: dict) -> dict:
    session = _session()
    name = seed["name"]
    found, unsupported = [], []

    link_hits = ats_hits("\n".join(seed.get("links", [])))
    found += [(ats, fields, "posting link") for ats, fields in link_hits]

    if not found and seed.get("website"):
        site_hits, unsupported = scan_website(session, seed["website"])
        found += [(ats, fields, "website") for ats, fields in site_hits]

    probed = not found
    if probed:
        found += [(ats, fields, "slug probe") for ats, fields in probe_candidates(name)]

    results = []
    for ats, fields, method in found:
        verified = verify(name, ats, fields)
        if verified is None:
            continue
        if method == "slug probe" and not verified["europe_internships"]:
            # Guessed slugs often hit a same-named different company (a
            # Danish Iveco dealer, a Zurich "RAI" institute); only worth
            # reviewing when there are internships to gain.
            continue
        if method != "slug probe":
            confidence = "high"
        elif ats == "greenhouse":
            board = filters.normalize_company(greenhouse_board_name(session, fields["slug"]))
            confidence = "medium" if board == filters.normalize_company(name) else "low"
        else:
            confidence = "low"
        results.append({**verified, "method": method, "confidence": confidence})
    return {"name": name, "seed": seed["seed"], "website": seed.get("website", ""),
            "candidates": results, "unsupported": unsupported, "checked": time.strftime("%Y-%m-%d")}


# --- output ------------------------------------------------------------------

def _yaml_value(value) -> str:
    text = str(value)
    return json.dumps(text) if re.search(r"[:#&*!|>'\"%@`{}\[\],]|^\s|\s$", text) or not text else text


def write_candidates(results: list[dict], path: str) -> int:
    rows = [(r, c) for r in results for c in r["candidates"]]
    rank = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda rc: (-rc[1]["target_role_internships"], -rc[1]["europe_internships"],
                              rank[rc[1]["confidence"]], rc[0]["name"]))
    lines = [
        "# Candidate watchlist entries from tools/discover_ats.py — REVIEW BEFORE COPYING.",
        "# Each was verified to return postings, but slug-probe hits (confidence",
        "# medium/low) may belong to a different company with the same slug: open",
        "# the sample posting / careers page before adding. Set `category` and",
        "# `priority`, then paste into companies.yaml (without the evidence comment).",
        "",
    ]
    for r, c in rows:
        entry = c["entry"]
        lines.append(
            f"# {c['confidence']} confidence via {c['method']} · {c['jobs']} jobs, "
            f"{c['europe_jobs']} in eligible countries, {c['europe_internships']} Europe internships ({c['target_role_internships']} target-role) · "
            f"seed: {r['seed']}"
        )
        lines.append(f"# sample: {c['sample']}")
        lines.append(f"- name: {_yaml_value(entry['name'])}")
        for key, value in entry.items():
            if key != "name":
                lines.append(f"  {key}: {_yaml_value(value)}")
        lines.append("")
    unsupported = [r for r in results if r["unsupported"] and not r["candidates"]]
    if unsupported:
        lines.append("# --- Careers pages on ATSs we can't scrape yet (custom scraper or manual check) ---")
        for r in sorted(unsupported, key=lambda r: r["name"]):
            lines.append(f"# {r['name']}: {', '.join(r['unsupported'])} ({r['website']})")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(rows)


def main_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="check at most N uncached companies this run")
    parser.add_argument("--countries", default="it", help="Wikidata countries, comma-separated ISO2 (default: it)")
    parser.add_argument("--no-wikidata", action="store_true", help="skip the Wikidata seed")
    parser.add_argument("--names", help="file with one company name per line (optionally 'name, website')")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache and re-check everything")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    watchlist = {filters.normalize_company(c.get("name", "")) for c in main.load_companies()}
    watch_slugs = {
        (c.get("ats"), str(c.get("slug") or c.get("tenant") or c.get("company_identifier") or "").lower())
        for c in main.load_companies()
    }

    seeds = seeds_from_csv(watchlist)
    if args.names:
        seeds += seeds_from_file(args.names)
    if not args.no_wikidata:
        countries = [c.strip().lower() for c in args.countries.split(",") if c.strip()]
        unknown = [c for c in countries if c not in _WIKIDATA_COUNTRIES]
        if unknown:
            parser.error(f"unknown country code(s): {', '.join(unknown)}")
        seeds += seeds_from_wikidata(countries)

    merged = {}
    for seed in seeds:
        key = filters.normalize_company(seed["name"])
        if not key or key in watchlist:
            continue
        existing = merged.setdefault(key, seed)
        if existing is not seed:
            existing["website"] = existing["website"] or seed["website"]
            existing["links"] += seed["links"]

    cache = {}
    if os.path.exists(_CACHE_PATH) and not args.refresh:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    todo = [seed for key, seed in merged.items() if key not in cache]
    cached = len(merged) - len(todo)
    if args.limit is not None:
        todo = todo[:args.limit]
    print(f"{len(merged)} seed companies ({cached} already checked); checking {len(todo)}.")

    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(discover, todo):
            cache[filters.normalize_company(result["name"])] = result
            done += 1
            if result["candidates"]:
                best = result["candidates"][0]
                print(f"[{done}/{len(todo)}] {result['name']}: {best['entry']['ats']} "
                      f"({best['confidence']}, {best['europe_internships']} Europe internships)")
            elif done % 25 == 0:
                print(f"[{done}/{len(todo)}] ...")
            if done % 25 == 0:
                with open(_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(cache, f, indent=1, ensure_ascii=False)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1, ensure_ascii=False)

    results = [
        {**r, "candidates": [
            c for c in r["candidates"]
            if (c["method"] != "slug probe" or c["europe_internships"])
            and (c["entry"]["ats"], str(c["entry"].get("slug") or c["entry"].get("tenant")
                                       or c["entry"].get("company_identifier") or "").lower()) not in watch_slugs
        ]}
        for key, r in cache.items() if key in merged
    ]
    count = write_candidates(results, _OUTPUT_PATH)
    print(f"Wrote {count} candidate(s) to {_OUTPUT_PATH}.")


if __name__ == "__main__":
    main_cli()
