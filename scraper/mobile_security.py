# scraper/mobile_security.py

"""
Mobile-friendliness and security analysis.

Mobile check relies on data the scraper already captured (viewport meta tag,
and a mobile-viewport render check done via Playwright). Security check is
pure logic based on the final URL scheme and any mixed-content resources
the scraper flagged.

Usage:
    from scraper.mobile_security import analyze_mobile_friendliness, analyze_security
"""

from urllib.parse import urlparse


def analyze_mobile_friendliness(page_data: dict) -> dict:
    """
    Expects page_data to include:
        "viewport_meta": str | None       — content of <meta name="viewport">
        "mobile_has_horizontal_scroll": bool | None  — set by scraper after
            rendering the page at a mobile viewport width; True means content
            overflows horizontally (a strong signal of a non-responsive page)

    Returns:
        {
            "has_viewport_meta": bool,
            "viewport_content": str | None,
            "viewport_configured_correctly": bool,
            "horizontal_scroll_on_mobile": bool | None,
        }
    """
    viewport_meta = page_data.get("viewport_meta")
    has_viewport_meta = bool(viewport_meta)

    # A correctly configured responsive viewport tag should include
    # "width=device-width" — without it, mobile browsers render at
    # a fixed desktop-like width and then scale down, which is the
    # classic "not mobile-friendly" symptom.
    viewport_configured_correctly = (
        has_viewport_meta and "width=device-width" in viewport_meta.replace(" ", "")
    )

    return {
        "has_viewport_meta": has_viewport_meta,
        "viewport_content": viewport_meta,
        "viewport_configured_correctly": viewport_configured_correctly,
        "horizontal_scroll_on_mobile": page_data.get("mobile_has_horizontal_scroll"),
    }


def analyze_security(page_data: dict) -> dict:
    """
    Expects page_data to include:
        "final_url": str
        "mixed_content_resources": list[str]  — http:// resource URLs found
            on an https:// page (set by the scraper)

    Returns:
        {
            "is_https": bool,
            "mixed_content_found": bool,
            "mixed_content_resources": list[str],
        }
    """
    final_url = page_data.get("final_url") or page_data.get("url", "")
    is_https = urlparse(final_url).scheme == "https"

    mixed_content = page_data.get("mixed_content_resources", []) if is_https else []

    return {
        "is_https": is_https,
        "mixed_content_found": len(mixed_content) > 0,
        "mixed_content_resources": mixed_content,
    }