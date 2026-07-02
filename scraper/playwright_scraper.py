# scraper/playwright_scraper.py

"""
Reusable Playwright-based scraper for the SEO Audit Tool.

Extracts everything needed for the full professional-level audit:
  - Standard on-page data: title, meta description, headings, images, links
  - Technical signals: canonical URL, robots meta/header, Open Graph, Twitter Card, structured data
  - Content: full visible body text, paragraph text (for keyword/readability analysis)
  - Performance: page load time, DOMContentLoaded time, approximate total page size
  - Mobile: viewport meta tag, horizontal-scroll check at a mobile viewport width
  - Security: HTTPS status (via final_url), mixed-content (http:// resources on an https:// page)

Errors are classified into an `error_type` so the frontend can show
tailored, user-friendly messages instead of a generic failure.

Usage:
    from scraper.playwright_scraper import scrape_page, PageScrapeError

    try:
        data = scrape_page("https://example.com")
    except PageScrapeError as e:
        print(e.error_type, e.message)
"""

from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class PageScrapeError(Exception):
    """
    Raised when a page cannot be loaded or scraped.

    error_type values:
        "timeout" | "dns_error" | "connection_refused" | "ssl_error" |
        "invalid_url" | "unknown"
    """
    def __init__(self, message, error_type="unknown"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


MOBILE_VIEWPORT = {"width": 390, "height": 844}  # iPhone 12-ish width


def _extract_page_data(page, response, url):
    """Runs all the DOM/network extraction for a single loaded page. Shared by
    the main desktop pass; kept as its own function so it's easy to test/read."""

    result = {}

    result["status_code"] = response.status
    result["final_url"] = response.url
    result["robots_header"] = response.headers.get("x-robots-tag")

    # --- Performance timing (Navigation Timing API) ---
    timing = page.evaluate("""() => {
        const nav = performance.getEntriesByType('navigation')[0];
        if (!nav) return null;
        return {
            load_time_ms: Math.round(nav.loadEventEnd - nav.startTime),
            dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd - nav.startTime),
        };
    }""")
    if timing:
        result["load_time_ms"] = timing["load_time_ms"] if timing["load_time_ms"] > 0 else None
        result["dom_content_loaded_ms"] = timing["dom_content_loaded_ms"] if timing["dom_content_loaded_ms"] > 0 else None
    else:
        result["load_time_ms"] = None
        result["dom_content_loaded_ms"] = None

    # --- Approximate total page size (sum of transferSize across all loaded resources) ---
    page_size_bytes = page.evaluate("""() => {
        const resources = performance.getEntriesByType('resource');
        let total = 0;
        for (const r of resources) {
            total += r.transferSize || 0;
        }
        const nav = performance.getEntriesByType('navigation')[0];
        if (nav) total += nav.transferSize || 0;
        return total;
    }""")
    result["page_size_bytes"] = page_size_bytes if page_size_bytes > 0 else None

    # --- Title ---
    result["title"] = page.title() or None

    # --- Meta description ---
    meta_desc = page.query_selector('meta[name="description"]')
    result["meta_description"] = meta_desc.get_attribute("content") if meta_desc else None

    # --- Headings ---
    result["h1_tags"] = [el.inner_text().strip() for el in page.query_selector_all("h1")]
    result["h2_tags"] = [el.inner_text().strip() for el in page.query_selector_all("h2")]

    # --- Body text + paragraphs (for keyword/content quality analysis) ---
    body_text = page.evaluate("""() => {
        const body = document.body;
        if (!body) return '';
        // Strip script/style/noscript content, which isn't visible text
        const clone = body.cloneNode(true);
        clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
        return clone.innerText || '';
    }""")
    result["body_text"] = body_text or ""

    result["paragraphs"] = [
        el.inner_text().strip() for el in page.query_selector_all("p")
        if el.inner_text().strip()
    ]

    # --- Images (src + alt) ---
    result["images"] = []
    for img in page.query_selector_all("img"):
        src = img.get_attribute("src")
        alt = img.get_attribute("alt")
        if src:
            result["images"].append({"src": src, "alt": alt})

    # --- Links (internal/external split + anchor text for quality checks) ---
    base_domain = urlparse(result["final_url"]).netloc
    result["links"] = {"internal": [], "external": []}
    result["links_with_text"] = []
    seen_links = set()

    for link in page.query_selector_all("a[href]"):
        href = link.get_attribute("href")
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        full_url = page.evaluate("(el) => el.href", link)
        anchor_text = link.inner_text().strip()

        if full_url not in seen_links:
            seen_links.add(full_url)
            link_domain = urlparse(full_url).netloc
            if link_domain == base_domain:
                result["links"]["internal"].append(full_url)
            else:
                result["links"]["external"].append(full_url)

        result["links_with_text"].append({"url": full_url, "text": anchor_text})

    # --- Canonical URL ---
    canonical_el = page.query_selector('link[rel="canonical"]')
    result["canonical_url"] = canonical_el.get_attribute("href") if canonical_el else None

    # --- Robots meta tags ---
    robots_el = page.query_selector('meta[name="robots"]')
    result["robots_meta"] = robots_el.get_attribute("content") if robots_el else None

    googlebot_el = page.query_selector('meta[name="googlebot"]')
    result["googlebot_meta"] = googlebot_el.get_attribute("content") if googlebot_el else None

    # --- Open Graph tags ---
    og_tags = {}
    for prop in ["og:title", "og:description", "og:image", "og:url", "og:type"]:
        el = page.query_selector(f'meta[property="{prop}"]')
        if el:
            og_tags[prop] = el.get_attribute("content")
    result["og_tags"] = og_tags

    # --- Twitter Card tags ---
    twitter_tags = {}
    for name in ["twitter:card", "twitter:title", "twitter:description", "twitter:image"]:
        el = page.query_selector(f'meta[name="{name}"]')
        if el:
            twitter_tags[name] = el.get_attribute("content")
    result["twitter_tags"] = twitter_tags

    # --- Structured data (JSON-LD) ---
    result["structured_data"] = [
        script.inner_text().strip()
        for script in page.query_selector_all('script[type="application/ld+json"]')
        if script.inner_text().strip()
    ]

    # --- Mobile: viewport meta tag ---
    viewport_el = page.query_selector('meta[name="viewport"]')
    result["viewport_meta"] = viewport_el.get_attribute("content") if viewport_el else None

    # --- Security: mixed content (http:// resources loaded on an https:// page) ---
    mixed_content = []
    if result["final_url"].startswith("https://"):
        resource_urls = page.evaluate("""() => {
            const urls = [];
            document.querySelectorAll('img[src], script[src], link[href]').forEach(el => {
                const url = el.src || el.href;
                if (url) urls.push(url);
            });
            return urls;
        }""")
        mixed_content = [u for u in resource_urls if u.startswith("http://")]
    result["mixed_content_resources"] = mixed_content

    return result


def _check_mobile_horizontal_scroll(browser, url, timeout):
    """
    Loads the page a second time at a mobile viewport width and checks
    whether the content overflows horizontally — a strong, simple signal
    that the page isn't actually responsive despite what its viewport
    meta tag might claim.

    Returns True/False, or None if this check couldn't be completed
    (e.g. the page failed to load the second time — treated as non-fatal,
    since the main scrape already succeeded).
    """
    try:
        mobile_context = browser.new_context(
            viewport=MOBILE_VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        mobile_page = mobile_context.new_page()
        mobile_page.goto(url, timeout=timeout, wait_until="domcontentloaded")

        has_overflow = mobile_page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        mobile_context.close()
        return bool(has_overflow)
    except Exception:
        return None


def scrape_page(url: str, timeout: int = 15000, headless: bool = True,
                 check_mobile_rendering: bool = True) -> dict:
    """
    Opens the given URL in a headless browser and extracts all SEO-relevant
    data: on-page tags, content text, performance metrics, links, mobile
    signals, and security signals.

    Args:
        url: The full URL to scrape (must include http:// or https://)
        timeout: Max time in milliseconds to wait for the page to load (default 15s)
        headless: Whether to run the browser without a visible window (default True)
        check_mobile_rendering: whether to do a second page load at a mobile
            viewport width to check for horizontal overflow. Adds a few
            seconds to the audit; set False for a faster, desktop-only scan.

    Returns:
        A dict with all fields described in the module docstring. See
        scraper.scoring.build_seo_report() for how this feeds into the
        final SEO report.

    Raises:
        PageScrapeError: if the page fails to load or times out.
    """

    result = {
        "url": url,
        "final_url": url,
        "status_code": None,
        "title": None,
        "meta_description": None,
        "h1_tags": [],
        "h2_tags": [],
        "body_text": "",
        "paragraphs": [],
        "images": [],
        "links": {"internal": [], "external": []},
        "links_with_text": [],
        "load_time_ms": None,
        "dom_content_loaded_ms": None,
        "page_size_bytes": None,
        "canonical_url": None,
        "robots_meta": None,
        "googlebot_meta": None,
        "robots_header": None,
        "og_tags": {},
        "twitter_tags": {},
        "structured_data": [],
        "viewport_meta": None,
        "mobile_has_horizontal_scroll": None,
        "mixed_content_resources": [],
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

            extracted = _extract_page_data(page, response, url)
            result.update(extracted)

        except PlaywrightTimeoutError:
            raise PageScrapeError(
                f"The site took too long to respond (over {timeout // 1000} seconds). "
                f"It may be slow, offline, or blocking automated visitors.",
                error_type="timeout"
            )

        except PageScrapeError:
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

        else:
            # Only attempt the mobile check if the main scrape succeeded
            if check_mobile_rendering:
                result["mobile_has_horizontal_scroll"] = _check_mobile_horizontal_scroll(
                    browser, result["final_url"], timeout
                )

        finally:
            browser.close()

    return result