import os
from dotenv import load_dotenv

load_dotenv()

SIMPLIFY_README_URL = os.getenv(
    "SIMPLIFY_README_URL",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md",
)

CSV_PATH = os.getenv("CSV_PATH", "internships.csv")
README_PATH = os.getenv("README_PATH", "README.md")
