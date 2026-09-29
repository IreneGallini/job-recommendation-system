from datetime import date

import pytest

import dates
import enrich
import filters
import ranking
from scrapers.base import Posting

TODAY = date(2026, 9, 29)


@pytest.mark.parametrize("raw, expected", [
    ("2026-08-17T10:00:00-04:00", "2026-08-17"),
    ("2026-09-11T08:12:00.000Z", "2026-09-11"),
    ("1757721600000", "2025-09-13"),  # Lever epoch ms
    ("Posted Today", "2026-09-29"),
    ("Posted Yesterday", "2026-09-28"),
    ("Posted 3 Days Ago", "2026-09-26"),
    ("Posted 30+ Days Ago", "2026-08-30"),
    ("", ""),
    ("not a date", ""),
])
def test_normalize_posted_date(raw, expected):
    assert dates.normalize_posted_date(raw, today=TODAY) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Milan, Italy", ("Milan", "Italy", filters.MILAN)),
    ("Milano", ("Milan", "Italy", filters.MILAN)),
    ("Assago Via del Mulino 11a", ("Assago", "Italy", filters.MILAN)),
    ("Torino, Italy", ("Turin", "Italy", filters.TURIN)),
    ("Rome, Italy", ("Rome", "Italy", filters.ITALY)),
    ("Germany, Munich", ("Munich", "Germany", filters.EUROPE)),  # Workday order
    ("Germany Munich", ("Munich", "Germany", filters.EUROPE)),  # Workday URL path
    ("Zürich, Schweiz", ("Zurich", "Switzerland", filters.EUROPE)),
    ("Segrate, Italy", ("Segrate", "Italy", filters.MILAN)),
    ("Wernau (Neckar), Germany", ("Wernau (Neckar)", "Germany", filters.EUROPE)),
    ("Paris, France; Milan, Italy", ("Milan", "Italy", filters.MILAN)),  # best of several
    ("Weinheim, DEU", ("Weinheim", "Germany", filters.EUROPE)),  # Workday ISO3
    ("Milano, ITA", ("Milan", "Italy", filters.MILAN)),
    ("Remote - Europe", ("", "", filters.REMOTE_EUROPE)),
])
def test_location_resolves(raw, expected):
    assert filters.normalize_location_text(raw) == expected


@pytest.mark.parametrize("raw", [
    "Bucharest, Romania",
    "Warsaw, Poland",
    "London, UK",
    "Belfast, Northern Ireland",  # UK, must not match "ireland"
    "Dublin, OH",  # US look-alikes
    "Vienna, VA",
    "Paris, TX",
    "Milan, Tennessee",
    "Tukwila, WA",
    "2 Locations",
    "",
])
def test_location_rejected(raw):
    assert filters.normalize_location_text(raw) is None


@pytest.mark.parametrize("title, internship", [
    ("Software Engineering Intern", True),
    ("Pflichtpraktikum Data Engineering", True),
    ("Stage Sales and Business Development", True),
    ("Werkstudent Finance", True),
    ("International Sales Manager", False),
    ("Internal Audit Specialist", False),
    ("Multi-stage Pipeline Engineer", False),
    ("Senior Software Engineer, Intern Tools", False),  # exclude keyword wins
])
def test_is_internship(title, internship):
    assert filters.is_internship(title) is internship


@pytest.mark.parametrize("text, months", [
    ("6-month internship in Milan", 6),
    ("Durata: 6 mesi", 6),
    ("sei mesi di stage", 6),
    ("12 weeks summer internship", 2.8),
    ("3-6 months", 3),  # lower bound of a range
    ("Dauer: mindestens 6 Monate", 6),
    ("3 years of experience required", None),
    ("no duration here", None),
])
def test_parse_duration(text, months):
    assert enrich.parse_duration(text) == months


@pytest.mark.parametrize("text, hint", [
    ("Summer Intern 2027", "summer"),
    ("stage estivo", "summer"),
    ("inizio settembre", "sep"),
    ("Beginn: ab Februar 2027", "feb"),
    ("Fecha de ingreso: febrero 2027", "feb"),
    ("starting in May", "may"),
    ("start date may vary", ""),  # modal verb, not the month
    ("inizio immediato", "sep"),  # ASAP -> reference month
])
def test_parse_start_hint(text, hint):
    assert enrich.parse_start_hint(text, reference=TODAY) == hint


@pytest.mark.parametrize("duration, start, fit", [
    (None, "summer", "yes"),
    (3, "may", "yes"),
    (4, "jun", "yes"),
    (6, "", "no"),
    (5, "summer", "no"),
    (3, "sep", "no"),
    (None, "feb", "no"),
    (3, "", "unknown"),
    (None, "jul", "unknown"),
    (None, "", "unknown"),
])
def test_summer_fit(duration, start, fit):
    assert enrich.summer_fit(duration, start) == fit


@pytest.mark.parametrize("text, req", [
    ("Currently enrolled in a Bachelor's or Master's degree", "any"),
    ("Master's student in Computer Science", "masters"),
    ("enrolled in a Master's or PhD program", "masters"),
    ("PhD candidate in chemistry", "phd"),
    ("laurea magistrale in ingegneria", "masters"),
    ("Scrum Master experience", "unknown"),
])
def test_degree_req(text, req):
    assert enrich.degree_req(text) == req


def _posting(**overrides) -> Posting:
    base = dict(
        company="X", role="Software Engineering Intern", location="Madrid, Spain",
        link="https://example.com/1", date_added="", source="test",
        city="Madrid", country="Spain", posted_date="2026-09-01",
    )
    base.update(overrides)
    return Posting(**base)


def test_ranking_prefers_milan_summer_over_long_elsewhere():
    milan_summer = _posting(link="a", city="Milan", country="Italy", summer_fit="yes")
    turin = _posting(link="b", city="Turin", country="Italy")
    madrid_long = _posting(link="c", summer_fit="no")
    phd = _posting(link="d", city="Milan", country="Italy", degree_req="phd")
    ranked = ranking.rank([madrid_long, phd, turin, milan_summer], today=TODAY)
    assert [p.link for p in ranked] == ["a", "b", "d", "c"]


def test_ranking_breaks_ties_by_newest():
    older = _posting(link="old", posted_date="2026-06-01")
    newer = _posting(link="new", posted_date="2026-06-02")
    assert [p.link for p in ranking.rank([older, newer], today=TODAY)] == ["new", "old"]


ADZUNA_JOB = {
    "id": "4812345678",
    "title": "Stage Data Analyst",
    "company": {"display_name": "Databricks Inc."},
    "location": {"display_name": "Segrate, Milano", "area": ["Italia", "Lombardia", "Milano", "Segrate"]},
    "redirect_url": "https://www.adzuna.it/land/ad/4812345678?se=abc&utm_medium=api&v=XYZ",
    "created": "2026-09-20T08:15:00Z",
    "description": "Stage di 6 mesi nel team dati...",
}


def test_adzuna_to_posting():
    from scrapers.adzuna import to_posting
    p = to_posting(ADZUNA_JOB, "Italy")
    assert p.company == "Databricks Inc."
    assert p.location == "Segrate, Italy"
    assert p.link == "https://www.adzuna.it/land/ad/4812345678"
    assert p.date_added == "2026-09-20"
    assert p.source == "Adzuna"
    [tagged] = filters.filter_and_tag([p])
    assert (tagged.city, tagged.country) == ("Segrate", "Italy")
    assert tagged.role_match


def test_adzuna_region_only_location():
    from scrapers.adzuna import to_posting
    job = dict(ADZUNA_JOB, location={"area": ["Italia", "Lombardia"]})
    assert to_posting(job, "Italy").location == "Italy"


@pytest.mark.parametrize("raw, expected", [
    ("Databricks Inc.", "databricks"),
    ("Intesa Sanpaolo S.p.A.", "intesa sanpaolo"),
    ("Accenture Italia", "accenture"),
    ("Bosch GmbH", "bosch"),
    ("Mistral AI", "mistral ai"),
    ("S.p.A.", "spa"),  # never reduced to nothing
])
def test_normalize_company(raw, expected):
    assert filters.normalize_company(raw) == expected


def test_adzuna_duplicate_of_ats_posting_dropped():
    import main
    from scrapers.adzuna import to_posting
    ats = Posting("Databricks", "Stage - Data Analyst", "Segrate, Italy",
                  "https://boards.greenhouse.io/databricks/jobs/1", "", "Databricks", ats="greenhouse")
    other = dict(ADZUNA_JOB, id="2", title="Stage Software Engineer",
                 redirect_url="https://www.adzuna.it/land/ad/2")
    eligible = filters.filter_and_tag([ats, to_posting(ADZUNA_JOB, "Italy"), to_posting(other, "Italy")])
    kept = main.drop_cross_source_duplicates(eligible, stored={})
    assert [p.source for p in kept] == ["Databricks", "Adzuna"]
    assert kept[1].role == "Stage Software Engineer"


def test_adzuna_inherits_watchlist_metadata():
    import main
    from scrapers.adzuna import to_posting
    p = to_posting(ADZUNA_JOB, "Italy")
    main.apply_watchlist_metadata([p], [
        {"name": "Databricks", "category": "big-tech", "priority": "high", "summer_program": True},
    ])
    assert (p.category, p.priority, p.summer_program) == ("big-tech", "high", True)


@pytest.mark.parametrize("text, expected", [
    ("https://job-boards.eu.greenhouse.io/scalapaysrl/jobs/123", ("greenhouse", {"slug": "scalapaysrl"})),
    ("https://boards.greenhouse.io/embed/job_board?for=databricks", ("greenhouse", {"slug": "databricks"})),
    ("https://jobs.eu.lever.co/prima/abc", ("lever", {"slug": "prima", "host": "api.eu.lever.co"})),
    ("https://jobs.ashbyhq.com/satispay", ("ashby", {"slug": "satispay"})),
    ("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/x",
     ("workday", {"tenant": "nvidia", "wd_host": "wd5", "site": "NVIDIAExternalCareerSite"})),
    ("https://jobs.smartrecruiters.com/BoschGroup/7", ("smartrecruiters", {"company_identifier": "BoschGroup"})),
    ("https://buddyfit.jobs.personio.com/job/1", ("personio", {"slug": "buddyfit", "host_suffix": "jobs.personio.com"})),
    ("https://apply.workable.com/moneyfarm/j/ABC", ("workable", {"slug": "moneyfarm"})),
    ("https://softswiss.teamtailor.com/jobs", ("teamtailor", {"slug": "softswiss"})),
])
def test_discover_ats_url_patterns(text, expected):
    from tools.discover_ats import ats_hits
    assert ats_hits(text)[0] == expected


def test_discover_unsupported_and_slugs():
    from tools.discover_ats import slug_variants, unsupported_hits
    assert unsupported_hits('<a href="https://career5.successfactors.eu/career?company=pirelli">') == ["SAP SuccessFactors"]
    assert slug_variants("Bending Spoons S.p.A.") == ["bendingspoons", "bending-spoons", "bending"]
    assert slug_variants("Mistral AI") == ["mistralai", "mistral-ai", "mistral"]
    assert slug_variants("The AI Co") == ["theai", "the-ai"]


def test_adzuna_city_from_title_when_region_only():
    from scrapers.adzuna import to_posting
    job = dict(ADZUNA_JOB, title="Software Engineer Intern - Milano", location={"area": ["Italia", "Lombardia"]})
    assert to_posting(job, "Italy").location == "Milan, Italy"
    job = dict(job, title="Software Engineer Intern - Paris")  # city in another country: ignored
    assert to_posting(job, "Italy").location == "Italy"


def test_adzuna_cityless_duplicate_dropped():
    import main
    from scrapers.adzuna import to_posting
    ats = Posting("Amazon", "2027 Software Dev Engineer Intern - Italy", "Milan, Italy",
                  "https://www.amazon.jobs/en/jobs/1", "", "Amazon", ats="amazon")
    job = dict(ADZUNA_JOB, title="2027 Software Dev Engineer Intern - Italy",
               company={"display_name": "Amazon"}, location={"area": ["Italia"]})
    eligible = filters.filter_and_tag([ats, to_posting(job, "Italy")])
    assert [p.source for p in main.drop_cross_source_duplicates(eligible, stored={})] == ["Amazon"]
