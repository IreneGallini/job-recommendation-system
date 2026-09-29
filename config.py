import os
from dotenv import load_dotenv

load_dotenv()

SIMPLIFY_README_URL = os.getenv(
    "SIMPLIFY_README_URL",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md",
)

CSV_PATH = os.getenv("CSV_PATH", "internships.csv")
README_PATH = os.getenv("README_PATH", "README.md")
COMPANIES_YAML_PATH = os.getenv("COMPANIES_YAML_PATH", "companies.yaml")
OUTREACH_YAML_PATH = os.getenv("OUTREACH_YAML_PATH", "outreach.yaml")
DOCS_DIR = os.getenv("DOCS_DIR", "docs")

# GitHub Pages site (docs/) with the Inbox / All / Outreach tabs; linked from
# the README.
SITE_URL = os.getenv("SITE_URL", "https://irenegallini.github.io/job-recommendation-system/")

# Optional: posts new postings to a Discord channel after each run. Skipped
# silently if unset.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Preferred commuting areas (lowercase). Postings in these towns are bucketed
# with Milan / Turin in the README and get the Milan / Turin ranking boost.
MILAN_AREA_CITIES = (
    "milan", "milano", "segrate", "assago", "sesto san giovanni", "monza",
    "rho", "san donato milanese", "cologno monzese", "basiglio", "pero",
    "cernusco sul naviglio", "vimercate", "agrate brianza", "lainate",
)
TURIN_AREA_CITIES = (
    "turin", "torino", "rivoli", "moncalieri", "collegno", "grugliasco",
    "orbassano", "settimo torinese", "nichelino", "chivasso", "ivrea",
)

# Multilingual "this is an internship" signal. A title must match one of
# these to be kept.
INTERN_KEYWORDS = (
    "intern", "internship", "stage", "stagista", "tirocinio", "tirocinante",
    "praktikum", "praktikant", "stagiaire", "prácticas", "practicas",
    "becario", "trainee", "summer student", "working student", "werkstudent",
)

# Titles matching any of these are dropped even if they also match an
# intern keyword above (guards against "Internship Program Manager" etc.).
EXCLUDE_KEYWORDS = (
    "senior", "staff", "principal", "director", "manager", "lead ",
    "new grad", "new college grad", "college graduate", "graduate program",
    "full-time only", "full time only",
)

# Target roles, English + Italian equivalents.
ROLE_KEYWORDS = (
    "software engineer", "software developer", "software engineering",
    "software dev", "software development", "sde intern",
    "backend", "back-end", "frontend", "front-end", "full stack", "full-stack",
    "ingegnere del software", "sviluppatore software", "sviluppatore",
    "sviluppo software", "softwareentwicklung", "softwareentwickler",
    "data science", "data scientist", "scienza dei dati",
    "data analyst", "analista dati", "analista di dati", "data analytics",
    "data analysis", "analisi dati", "business intelligence",
    "data engineer", "ingegnere dei dati",
    "ml engineer", "machine learning engineer", "machine learning",
    "ai engineer", "artificial intelligence", "intelligenza artificiale",
    "applied ai", "generative ai", "genai", "ai/ml", "applied scientist",
)

# Bonus-interest roles (computational chemistry / drug discovery / pharma
# data); a title matching one of these also passes the role filter.
CHEM_BIO_KEYWORDS = (
    "computational chemistry", "chimica computazionale",
    "drug discovery", "cheminformatics", "bioinformatics",
    "bioinformatica", "biotech data", "pharma data",
    "computational biology", "biologia computazionale",
)

# Recommendation score weights (see ranking.py). Tune these to change how
# the site's Inbox, the README and Discord are ordered.
SCORE_WEIGHTS = {
    "milan": 40,
    "turin": 35,
    "italy": 20,
    "remote_europe": 5,
    "summer_fit_yes": 25,
    "summer_fit_no": -30,
    "summer_program": 10,
    "priority_high": 10,
    "role_match": 20,
    "chem_bio": 5,
    "degree_phd": -25,
    "degree_masters": -15,
    "recency_max": 10,  # fades linearly to 0 over RECENCY_DAYS
}
RECENCY_DAYS = 30
