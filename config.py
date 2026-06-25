import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_APP_PASSWORD = os.environ["EMAIL_APP_PASSWORD"]

SIMPLIFY_README_URL = os.getenv(
    "SIMPLIFY_README_URL",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md",
)

CSV_PATH = os.getenv("CSV_PATH", "internships.csv")
