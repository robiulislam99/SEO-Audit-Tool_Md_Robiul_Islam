# scraper/playwright_scraper.py

"""
Reusable Playwright-based scraper for the SEO Audit Tool.

Extracts: title, meta description, headings (H1/H2), images (with alt text),
and links (internal/external) from a given URL.

Errors are classified into an `error_type` so the frontend can show
tailored, user-friendly messages instead of a generic failure.

Usage:
    from scraper.playwright_scraper import scrape_page, PageScrapeError

    try:
        data = scrape_page("https://example.com")
        print(data["title"])
    except PageScrapeError as e:
        print(e.error_type, e.message)
"""

from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class PageScrapeError(Exception):
    """
    Raised when a page cannot be loaded or scraped.

    error_type is a machine-readable category the frontend can key off of
    to show a tailored message/icon, instead of one generic error string.

    Possible values:
        "timeout"             - page took too long to respond
        "dns_error"           - domain could not be resolved (typo, doesn't exist)
        "connection_refused"  - site is down or actively refusing connections
        "ssl_error"           - certificate/HTTPS problem
        "invalid_url"         - malformed URL, never reached the network
        "unknown"             - anything else / unexpected
    """
    def __init__(self, message, error_type="unknown"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


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
                          Check e.error_type for the specific category.
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
                raise PageScrapeError(
                    "The site didn't send back any response.",
                    error_type="connection_refused"
                )

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

                # Resolve relative URLs against the page (browser does the join for us)
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
            raise PageScrapeError(
                f"The site took too long to respond (over {timeout // 1000} seconds). "
                f"It may be slow, offline, or blocking automated visitors.",
                error_type="timeout"
            )

        except PageScrapeError:
            # Already classified above (e.g. the "no response" case) — just re-raise as-is
            raise

        except Exception as e:
            error_str = str(e).lower()

            if "err_name_not_resolved" in error_str or "dns" in error_str:
                raise PageScrapeError(
                    "We couldn't find that website. Double-check the URL is spelled correctly.",
                    error_type="dns_error"
                )
            elif "err_connection_refused" in error_str:
                raise PageScrapeError(
                    "The site refused the connection. It may be down or blocking automated tools.",
                    error_type="connection_refused"
                )
            elif "net::err_cert" in error_str or "ssl" in error_str:
                raise PageScrapeError(
                    "This site has an SSL/certificate problem, so we couldn't load it securely.",
                    error_type="ssl_error"
                )
            elif "invalid url" in error_str or "err_invalid_url" in error_str:
                raise PageScrapeError(
                    "That doesn't look like a valid URL.",
                    error_type="invalid_url"
                )
            else:
                raise PageScrapeError(
                    "Something went wrong while loading this page.",
                    error_type="unknown"
                )

        finally:
            browser.close()

    return result