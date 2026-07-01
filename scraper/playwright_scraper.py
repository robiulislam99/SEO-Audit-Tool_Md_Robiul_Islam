# scraper/playwright_scraper.py

"""
Reusable Playwright-based scraper for the SEO Audit Tool.

Extracts: title, meta description, headings (H1/H2), images (with alt text),
and links (internal/external) from a given URL.

Usage:
    from scraper.playwright_scraper import scrape_page

    data = scrape_page("https://example.com")
    print(data["title"])
"""

from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class PageScrapeError(Exception):
    """Raised when a page cannot be loaded or scraped."""
    pass


def scrape_page(url: str, timeout: int = 15000, headless: bool = True) -> dict:
    """
    Opens the given URL in a headless browser and extracts SEO-relevant data.

    Args:
        url: The full URL to scrape (must include http:// or https://)
        timeout: Max time in milliseconds to wait for the page to load (default 15s)
        headless: Whether to run the browser without a visible window (default True)

    Returns:
        A dictionary with the following structure:
        {
            "url": str,
            "status_code": int,
            "title": str | None,
            "meta_description": str | None,
            "h1_tags": list[str],
            "h2_tags": list[str],
            "images": [{"src": str, "alt": str | None}, ...],
            "links": {
                "internal": list[str],
                "external": list[str],
            },
            "load_time_ms": int,
        }

    Raises:
        PageScrapeError: if the page fails to load or times out.
    """

    result = {
        "url": url,
        "status_code": None,
        "title": None,
        "meta_description": None,
        "h1_tags": [],
        "h2_tags": [],
        "images": [],
        "links": {"internal": [], "external": []},
        "load_time_ms": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (compatible; SEOAuditBot/1.0; +https://example.com/bot)"
        )
        page = context.new_page()

        try:
            response = page.goto(url, timeout=timeout, wait_until="domcontentloaded")

            if response is None:
                raise PageScrapeError(f"No response received from {url}")

            result["status_code"] = response.status
            timing = page.evaluate(
                "() => performance.timing.loadEventEnd - performance.timing.navigationStart"
            )
            result["load_time_ms"] = timing if timing and timing > 0 else None

            # --- Title ---
            result["title"] = page.title() or None

            # --- Meta description ---
            meta_desc = page.query_selector('meta[name="description"]')
            if meta_desc:
                result["meta_description"] = meta_desc.get_attribute("content")

            # --- Headings ---
            result["h1_tags"] = [
                el.inner_text().strip() for el in page.query_selector_all("h1")
            ]
            result["h2_tags"] = [
                el.inner_text().strip() for el in page.query_selector_all("h2")
            ]

            # --- Images (src + alt) ---
            for img in page.query_selector_all("img"):
                src = img.get_attribute("src")
                alt = img.get_attribute("alt")
                if src:  # skip images with no src at all
                    result["images"].append({"src": src, "alt": alt})

            # --- Links (split internal vs external) ---
            base_domain = urlparse(url).netloc
            seen_links = set()

            for link in page.query_selector_all("a[href]"):
                href = link.get_attribute("href")
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue

                # Resolve relative URLs against the page
                full_url = page.evaluate("(el) => el.href", link)

                if full_url in seen_links:
                    continue
                seen_links.add(full_url)

                link_domain = urlparse(full_url).netloc
                if link_domain == base_domain:
                    result["links"]["internal"].append(full_url)
                else:
                    result["links"]["external"].append(full_url)

        except PlaywrightTimeoutError:
            raise PageScrapeError(f"Timed out while loading {url}")
        except Exception as e:
            raise PageScrapeError(f"Failed to scrape {url}: {str(e)}")
        finally:
            browser.close()

    return result