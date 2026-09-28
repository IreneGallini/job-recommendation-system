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

# Optional: posts new postings to a Discord channel after each run. Skipped
# silently if unset.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

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
    "ingegnere del software", "sviluppatore software",
    "data science", "data scientist", "scienza dei dati",
    "data analyst", "analista dati", "analista di dati",
    "data engineer", "ingegnere dei dati",
    "ml engineer", "machine learning engineer", "machine learning",
    "ai engineer", "artificial intelligence", "intelligenza artificiale",
)

# Bonus-interest roles (computational chemistry / drug discovery / pharma
# data); a title matching one of these also passes the role filter.
CHEM_BIO_KEYWORDS = (
    "computational chemistry", "chimica computazionale",
    "drug discovery", "cheminformatics", "bioinformatics",
    "bioinformatica", "biotech data", "pharma data",
    "computational biology", "biologia computazionale",
)
