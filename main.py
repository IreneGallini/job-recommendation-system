import sys
import config
from scrapers.simplify_github import SimplifyGitHubScraper
from scrapers.nvidia_careers import NvidiaCareersScraper
from storage.csv_store import load_seen_links, load_all_postings, append_new_postings
from storage.readme_table import write_postings_table


def main() -> None:
    scrapers = [
        SimplifyGitHubScraper(config.SIMPLIFY_README_URL),
        NvidiaCareersScraper(),
    ]

    all_postings = []
    for scraper in scrapers:
        source_name = type(scraper).__name__
        try:
            postings = scraper.get_postings()
        except Exception as e:
            print(f"ERROR: {source_name} failed: {e}", file=sys.stderr)
            continue
        print(f"{source_name}: {len(postings)} posting(s).")
        all_postings.extend(postings)

    if not all_postings:
        print("ERROR: No postings fetched from any source.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(all_postings)} total postings across all sources.")

    seen = load_seen_links(config.CSV_PATH)
    new_postings = [p for p in all_postings if p.link not in seen]

    print(f"{len(new_postings)} new posting(s) since last run.")

    if new_postings:
        append_new_postings(config.CSV_PATH, new_postings)
        print(f"Saved to {config.CSV_PATH}.")
        write_postings_table(config.README_PATH, load_all_postings(config.CSV_PATH))
        print(f"Updated postings table in {config.README_PATH}.")
    else:
        print("No new postings.")


if __name__ == "__main__":
    main()
