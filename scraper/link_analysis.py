# scraper/link_analysis.py

"""
Link analysis: checks internal/external links for broken status codes,
and flags low-quality anchor text (e.g. "click here", empty links).

Broken-link checking makes real HTTP requests, so it's the slowest part
of an audit. To keep audits fast, only a capped number of links are
checked (default 20) rather than every link on the page.

Usage:
    from scraper.link_analysis import analyze_links

    result = analyze_links(page_data, max_links_to_check=20)
"""

import requests

# Anchor text phrases that carry no SEO/accessibility value on their own —
# a screen reader user or search engine gets no context from these.
GENERIC_ANCHOR_PHRASES = {
    "click here", "here", "read more", "more", "link", "this link",
    "learn more", "click", "this page", "page", "download",
}

LINK_CHECK_TIMEOUT = 5  # seconds per link — keep short so a few slow links don't stall the whole audit


def check_link_status(url: str) -> dict:
    """
    Checks a single URL's HTTP status. Uses HEAD first (cheaper — no body
    download); falls back to GET if the server doesn't support HEAD
    properly (some servers return 405 or block HEAD requests entirely).
    """
    try:
        resp = requests.head(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400 or resp.status_code == 405:
            resp = requests.get(url, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True, stream=True)
        return {"url": url, "status_code": resp.status_code, "ok": resp.status_code < 400, "error": None}
    except requests.exceptions.Timeout:
        return {"url": url, "status_code": None, "ok": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"url": url, "status_code": None, "ok": False, "error": "connection_error"}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status_code": None, "ok": False, "error": str(e)}


def find_broken_links(links: list, max_links_to_check: int = 20) -> list:
    """
    Checks up to max_links_to_check links (internal links prioritized,
    since those are within the site owner's control to fix) and returns
    only the ones that are broken.
    """
    checked = 0
    broken = []

    for url in links[:max_links_to_check]:
        result = check_link_status(url)
        checked += 1
        if not result["ok"]:
            broken.append(result)

    return broken


def analyze_anchor_texts(links_with_text: list) -> list:
    """
    Flags links with low-quality anchor text.

    Args:
        links_with_text: [{"url": str, "text": str}, ...]

    Returns:
        list of flagged issues: [{"url", "text", "issue"}, ...]
    """
    issues = []

    for link in links_with_text:
        text = (link.get("text") or "").strip()
        url = link.get("url", "")

        if not text:
            issues.append({"url": url, "text": "", "issue": "empty_anchor_text"})
        elif text.lower() in GENERIC_ANCHOR_PHRASES:
            issues.append({"url": url, "text": text, "issue": "generic_anchor_text"})
        elif text.lower().startswith(("http://", "https://", "www.")):
            issues.append({"url": url, "text": text, "issue": "raw_url_as_anchor_text"})

    return issues


def analyze_links(page_data: dict, max_links_to_check: int = 20, check_broken: bool = True) -> dict:
    """
    Main entry point for link analysis.

    Expects page_data["links"] = {"internal": [...urls], "external": [...urls]}
    and optionally page_data["links_with_text"] = [{"url", "text"}, ...] for
    anchor text quality checks.

    Returns:
        {
            "internal_count": int,
            "external_count": int,
            "broken_links": [{"url", "status_code", "ok", "error"}, ...],
            "anchor_text_issues": [{"url", "text", "issue"}, ...],
            "links_checked_for_broken": int,
        }
    """
    links = page_data.get("links", {"internal": [], "external": []})
    internal = links.get("internal", [])
    external = links.get("external", [])

    result = {
        "internal_count": len(internal),
        "external_count": len(external),
        "broken_links": [],
        "anchor_text_issues": [],
        "links_checked_for_broken": 0,
    }

    if check_broken:
        # Prioritize internal links (site owner can actually fix these),
        # then fill remaining budget with external links.
        all_links = internal + external
        links_to_check = all_links[:max_links_to_check]
        result["broken_links"] = find_broken_links(links_to_check, max_links_to_check)
        result["links_checked_for_broken"] = len(links_to_check)

    links_with_text = page_data.get("links_with_text", [])
    if links_with_text:
        result["anchor_text_issues"] = analyze_anchor_texts(links_with_text)

    return result