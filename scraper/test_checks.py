from scraper.checks import analyze_seo
from scraper.playwright_scraper import scrape_page


def main() -> None:
    page_data = scrape_page("https://example.com")
    analysis = analyze_seo(page_data, target_keyword="example domain")

    print("Score:", analysis["score"])
    print("\nSuggestions:")
    for suggestion in analysis["suggestions"]:
        print(" -", suggestion)


if __name__ == "__main__":
    main()