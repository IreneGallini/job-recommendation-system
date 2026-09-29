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
