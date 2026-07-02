# scraper/checks.py

"""
SEO analysis engine. Each check returns:
{
    check_name, category, severity ("pass"|"warning"|"fail"),
    passed (bool, True only if severity == "pass"),
    weight, message, affected_element, recommendation
}
"""

import json
from urllib.parse import urlparse


def _result(check_name, category, severity, weight, message,
            affected_element=None, recommendation=None, skipped=False):
    return {
        "check_name": check_name,
        "category": category,
        "severity": severity,
        "passed": severity == "pass",
        "weight": weight,
        "message": message,
        "affected_element": affected_element,
        "recommendation": recommendation,
        "skipped": skipped,
    }


# ---------- On-page checks ----------

def check_title(page_data):
    title = (page_data.get("title") or "").strip()
    length = len(title)

    if not title:
        return _result("title_tag", "on_page", "fail", 10,
                        "Missing <title> tag.",
                        affected_element="<title>",
                        recommendation="Add a unique, descriptive <title> tag between 50-60 characters.")

    if length < 50:
        return _result("title_tag", "on_page", "warning", 6,
                        f"Title is short ({length} chars).",
                        affected_element=f"<title>{title}</title>",
                        recommendation="Expand the title to 50-60 characters for better search visibility.")

    if length > 60:
        return _result("title_tag", "on_page", "warning", 6,
                        f"Title is long ({length} chars) and may be truncated in search results.",
                        affected_element=f"<title>{title}</title>",
                        recommendation="Shorten the title to under 60 characters.")

    return _result("title_tag", "on_page", "pass", 10, f"Title length is good ({length} chars).")


def check_meta_description(page_data):
    desc = (page_data.get("meta_description") or "").strip()
    length = len(desc)

    if not desc:
        return _result("meta_description", "on_page", "fail", 10,
                        "Missing meta description.",
                        affected_element='<meta name="description">',
                        recommendation="Add a meta description of 150-160 characters summarizing the page.")

    if length < 150:
        return _result("meta_description", "on_page", "warning", 6,
                        f"Meta description is short ({length} chars).",
                        affected_element=f'<meta name="description" content="{desc[:60]}...">',
                        recommendation="Expand the description to 150-160 characters.")

    if length > 160:
        return _result("meta_description", "on_page", "warning", 6,
                        f"Meta description is long ({length} chars) and may be truncated.",
                        affected_element=f'<meta name="description" content="{desc[:60]}...">',
                        recommendation="Shorten the description to under 160 characters.")

    return _result("meta_description", "on_page", "pass", 10, f"Meta description length is good ({length} chars).")


def check_image_optimization(page_data):
    images = page_data.get("images", [])

    if not images:
        return _result("image_optimization", "technical", "pass", 0, "No images found on this page.")

    missing_alt = [img for img in images if not img.get("alt") or not img["alt"].strip()]
    large_images = []

    for img in images:
        natural_width = img.get("natural_width") or 0
        natural_height = img.get("natural_height") or 0
        rendered_width = img.get("client_width") or 0
        rendered_height = img.get("client_height") or 0

        if (
            natural_width >= 1600
            or natural_height >= 1600
            or (natural_width * natural_height) >= 2_000_000
            or (rendered_width * rendered_height) >= 900_000
        ):
            large_images.append(img)

    if not missing_alt and not large_images:
        return _result("image_optimization", "technical", "pass", 8,
                        f"All {len(images)} image(s) have alt text and no unusually large images were detected.")

    issues = []
    if missing_alt:
        issues.append(f"{len(missing_alt)} missing alt text")
    if large_images:
        issues.append(f"{len(large_images)} large image(s)")

    example = large_images[0] if large_images else missing_alt[0]
    affected = example.get("src", "unknown")
    if example.get("natural_width") and example.get("natural_height"):
        affected = f'{affected} ({example["natural_width"]}x{example["natural_height"]})'

    severity = "fail" if large_images and len(large_images) > 1 else "warning"
    weight = 8 if severity == "fail" else 5

    recommendation_parts = []
    if missing_alt:
        recommendation_parts.append("Add descriptive alt text to every image.")
    if large_images:
        recommendation_parts.append("Resize and compress oversized images before publishing.")

    return _result(
        "image_optimization",
        "technical",
        severity,
        weight,
        f"Image optimization issues detected: {', '.join(issues)}.",
        affected_element=affected,
        recommendation=" ".join(recommendation_parts),
    )


def check_heading_structure(page_data):
    h1_tags = page_data.get("h1_tags", [])
    h2_tags = page_data.get("h2_tags", [])

    if len(h1_tags) == 0:
        return _result("heading_structure", "on_page", "fail", 10,
                        "No H1 tag found.",
                        affected_element="<h1>",
                        recommendation="Add exactly one H1 tag that clearly describes the page's main topic.")

    if len(h1_tags) > 1:
        return _result("heading_structure", "on_page", "warning", 6,
                        f"Multiple H1 tags found ({len(h1_tags)}).",
                        affected_element="<h1>",
                        recommendation="Use only one H1 per page; convert extras to H2.")

    if len(h2_tags) == 0:
        return _result("heading_structure", "on_page", "warning", 4,
                        "No H2 tags found.",
                        affected_element="<h2>",
                        recommendation="Add H2 subheadings to break up content and aid readability.")

    return _result("heading_structure", "on_page", "pass", 10,
                    f"Good heading structure: 1 H1, {len(h2_tags)} H2(s).")


def check_image_alt_text(page_data):
    images = page_data.get("images", [])

    if not images:
        return _result("image_alt_text", "on_page", "pass", 5, "No images found on this page.")

    missing_alt = [img for img in images if not img.get("alt") or not img["alt"].strip()]
    missing_count = len(missing_alt)
    total_count = len(images)

    if missing_count == 0:
        return _result("image_alt_text", "on_page", "pass", 10, f"All {total_count} image(s) have alt text.")

    ratio_missing = missing_count / total_count
    example_src = missing_alt[0].get("src", "unknown")

    severity = "fail" if ratio_missing > 0.5 else "warning"
    weight = 10 if severity == "fail" else 6

    return _result("image_alt_text", "on_page", severity, weight,
                    f"{missing_count} of {total_count} images are missing alt text.",
                    affected_element=f'<img src="{example_src}"> (+{missing_count - 1} more)' if missing_count > 1 else f'<img src="{example_src}">',
                    recommendation="Add descriptive alt text to every image for accessibility and image SEO.")


def check_keyword_usage(page_data, target_keyword=None):
    if not target_keyword:
        return _result("keyword_usage", "on_page", "pass", 0,
                        "No target keyword provided — skipped.", skipped=True)

    keyword = target_keyword.lower().strip()
    title = (page_data.get("title") or "").lower()
    meta_desc = (page_data.get("meta_description") or "").lower()
    h1_text = " ".join(page_data.get("h1_tags", [])).lower()

    hits = sum([keyword in title, keyword in meta_desc, keyword in h1_text])

    if hits == 0:
        return _result("keyword_usage", "on_page", "fail", 10,
                        f'Keyword "{target_keyword}" not found in title, meta description, or H1.',
                        recommendation=f'Include "{target_keyword}" naturally in the title, meta description, and H1.')

    if hits == 3:
        return _result("keyword_usage", "on_page", "pass", 10,
                        f'Keyword "{target_keyword}" appears in title, meta description, and H1.')

    return _result("keyword_usage", "on_page", "warning", 6,
                    f'Keyword "{target_keyword}" is only partially used ({hits}/3 key locations).',
                    recommendation=f'Add "{target_keyword}" to the remaining title/meta/H1 locations.')


def check_internal_links(page_data):
    internal = page_data.get("links", {}).get("internal", [])

    if len(internal) == 0:
        return _result("internal_links", "technical", "fail", 5,
                        "No internal links found.",
                        recommendation="Add links to other relevant pages on your site to improve crawlability.")

    if len(internal) < 3:
        return _result("internal_links", "technical", "warning", 3,
                        f"Only {len(internal)} internal link(s) found.",
                        recommendation="Add more internal links to strengthen site structure.")

    return _result("internal_links", "technical", "pass", 5, f"{len(internal)} internal links found.")


# ---------- Technical checks ----------

def _normalize_url_for_comparison(url):
    """
    Normalizes a URL for loose comparison: lowercases the host, strips a
    trailing slash, and drops query string/fragment. This avoids false
    positives when comparing scheme/www variants that are functionally
    the same page (e.g. http://example.com vs https://www.example.com/).
    """
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def check_canonical_url(page_data):
    """
    Compares the canonical tag against the page's FINAL URL (after any
    redirects), not the raw URL the user typed. This matters because sites
    routinely redirect http->https or bare-domain->www, and a canonical tag
    pointing to that redirected destination is correct, expected behavior —
    not something that should be flagged as "pointing elsewhere".
    """
    canonical = page_data.get("canonical_url")

    if not canonical:
        return _result("canonical_url", "technical", "warning", 5,
                        "No canonical tag found.",
                        affected_element='<link rel="canonical">',
                        recommendation="Add a canonical tag to prevent duplicate content issues.")

    # Prefer final_url (post-redirect); fall back to url if a caller
    # is using an older page_data shape that doesn't have it yet.
    reference_url = page_data.get("final_url") or page_data.get("url", "")

    canonical_normalized = _normalize_url_for_comparison(canonical)
    reference_normalized = _normalize_url_for_comparison(reference_url)

    if canonical_normalized != reference_normalized:
        return _result("canonical_url", "technical", "warning", 3,
                        f"Canonical URL points elsewhere: {canonical}",
                        affected_element=f'<link rel="canonical" href="{canonical}">',
                        recommendation="Verify this is intentional — otherwise point the canonical tag to this exact page.")

    return _result("canonical_url", "technical", "pass", 5, "Canonical tag is present and self-referencing.")


def check_robots_meta(page_data):
    """
    Checks all three places a page can be told not to index, in order of
    how commonly they're used:
      1. <meta name="robots" content="noindex">      - the standard tag
      2. <meta name="googlebot" content="noindex">    - Google-specific override
      3. X-Robots-Tag: noindex (HTTP response header) - can block indexing
         with no visible HTML trace at all
    Any one of these being set to noindex means the page won't be indexed,
    regardless of what the other two say.
    """
    robots_meta = (page_data.get("robots_meta") or "").lower()
    googlebot_meta = (page_data.get("googlebot_meta") or "").lower()
    robots_header = (page_data.get("robots_header") or "").lower()

    if "noindex" in robots_meta:
        return _result("robots_meta", "technical", "fail", 10,
                        "Page is set to 'noindex' via meta tag — it will NOT appear in search results.",
                        affected_element=f'<meta name="robots" content="{robots_meta}">',
                        recommendation="Remove 'noindex' if you want this page to be discoverable in search engines.")

    if "noindex" in googlebot_meta:
        return _result("robots_meta", "technical", "fail", 10,
                        "Page is set to 'noindex' specifically for Googlebot — it will NOT appear in Google search results.",
                        affected_element=f'<meta name="googlebot" content="{googlebot_meta}">',
                        recommendation="Remove 'noindex' from the googlebot meta tag if you want this page indexed by Google.")

    if "noindex" in robots_header:
        return _result("robots_meta", "technical", "fail", 10,
                        "Page is set to 'noindex' via the X-Robots-Tag HTTP header — it will NOT appear in search results.",
                        affected_element=f"X-Robots-Tag: {robots_header}",
                        recommendation="Remove 'noindex' from the X-Robots-Tag response header if you want this page indexed.")

    if robots_meta or googlebot_meta or robots_header:
        return _result("robots_meta", "technical", "pass", 5,
                        "Robots directives are present and do not block indexing.")

    return _result("robots_meta", "technical", "pass", 5,
                    "No robots-blocking directive found — page is indexable by default.")


# ---------- Social checks ----------

def check_open_graph(page_data):
    og = page_data.get("og_tags", {})
    required = ["og:title", "og:description", "og:image"]
    missing = [tag for tag in required if tag not in og]

    if len(missing) == len(required):
        return _result("open_graph", "social", "fail", 6,
                        "No Open Graph tags found.",
                        recommendation="Add og:title, og:description, and og:image so shared links look good on social media.")

    if missing:
        return _result("open_graph", "social", "warning", 3,
                        f"Missing Open Graph tags: {', '.join(missing)}.",
                        recommendation=f"Add the missing tag(s): {', '.join(missing)}.")

    return _result("open_graph", "social", "pass", 6, "All key Open Graph tags are present.")


def check_twitter_card(page_data):
    twitter = page_data.get("twitter_tags", {})

    if not twitter:
        return _result("twitter_card", "social", "warning", 3,
                        "No Twitter Card tags found.",
                        recommendation="Add twitter:card, twitter:title, and twitter:description for better previews on X/Twitter.")

    if "twitter:card" not in twitter:
        return _result("twitter_card", "social", "warning", 2,
                        "twitter:card type is not specified.",
                        recommendation='Add <meta name="twitter:card" content="summary_large_image"> or similar.')

    return _result("twitter_card", "social", "pass", 3, "Twitter Card tags are present.")


# ---------- Structured data ----------

def check_structured_data(page_data):
    blocks = page_data.get("structured_data", [])

    if not blocks:
        return _result("structured_data", "structured_data", "warning", 5,
                        "No structured data (Schema.org / JSON-LD) found.",
                        recommendation="Add JSON-LD structured data relevant to your content type (Article, Product, Organization, etc.) to enable rich search results.")

    valid_count = 0
    for block in blocks:
        try:
            json.loads(block)
            valid_count += 1
        except (json.JSONDecodeError, TypeError):
            pass

    if valid_count == 0:
        return _result("structured_data", "structured_data", "fail", 5,
                        f"Found {len(blocks)} structured data block(s), but none are valid JSON.",
                        affected_element='<script type="application/ld+json">',
                        recommendation="Fix the JSON syntax in your structured data blocks.")

    return _result("structured_data", "structured_data", "pass", 5,
                    f"{valid_count} valid structured data block(s) found.")


# ---------- Main entry point ----------

def analyze_seo(page_data, target_keyword=None):
    checks = [
        check_title(page_data),
        check_meta_description(page_data),
        check_heading_structure(page_data),
        check_image_alt_text(page_data),
        check_image_optimization(page_data),
        check_keyword_usage(page_data, target_keyword),
        check_internal_links(page_data),
        check_canonical_url(page_data),
        check_robots_meta(page_data),
        check_open_graph(page_data),
        check_twitter_card(page_data),
        check_structured_data(page_data),
    ]

    scored_checks = [c for c in checks if not c.get("skipped")]
    total_weight = sum(c["weight"] for c in scored_checks)
    earned_weight = sum(c["weight"] for c in scored_checks if c["severity"] == "pass")

    score = round((earned_weight / total_weight) * 100) if total_weight > 0 else 0

    suggestions = [c["message"] for c in checks if c["severity"] != "pass" and not c.get("skipped")]

    return {"score": score, "results": checks, "suggestions": suggestions}