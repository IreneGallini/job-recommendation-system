import sys
import config
from scrapers.simplify_github import SimplifyGitHubScraper
from storage.csv_store import load_seen_links, append_new_postings
from notifiers.email_notifier import send_digest


def main() -> None:
    print(f"Fetching postings from: {config.SIMPLIFY_README_URL}")
    scraper = SimplifyGitHubScraper(config.SIMPLIFY_README_URL)

    try:
        all_postings = scraper.get_postings()
    except Exception as e:
        print(f"ERROR: Failed to fetch postings: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(all_postings)} total postings in source.")

    seen = load_seen_links(config.CSV_PATH)
    new_postings = [p for p in all_postings if p.link not in seen]

    print(f"{len(new_postings)} new posting(s) since last run.")

    if new_postings:
        append_new_postings(config.CSV_PATH, new_postings)
        print(f"Saved to {config.CSV_PATH}.")
        send_digest(new_postings, config.EMAIL_ADDRESS, config.EMAIL_APP_PASSWORD)
        print(f"Email sent to {config.EMAIL_ADDRESS}.")
    else:
        print("No new postings. No email sent.")


if __name__ == "__main__":
    main()
