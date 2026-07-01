from scraper.playwright_scraper import PageScrapeError, scrape_page


def main() -> None:
    try:
        data = scrape_page("https://example.com")
        print("Title:", data["title"])
        print("Meta description:", data["meta_description"])
        print("H1 count:", len(data["h1_tags"]))
        print("H2 count:", len(data["h2_tags"]))
        print("Images:", len(data["images"]))
        print("Internal links:", len(data["links"]["internal"]))
        print("External links:", len(data["links"]["external"]))
    except PageScrapeError as e:
        print("Scrape failed:", e)


if __name__ == "__main__":
    main()