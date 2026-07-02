# scraper/scoring.py

"""
Master SEO scoring engine.

Combines all individual checks (on-page/technical, keyword, content quality,
links, mobile, security, performance) into three weighted category scores
— Technical SEO, Content SEO, Performance — plus one overall 0-100 score.

This is the single entry point Django's background task should call.

Usage:
    from scraper.scoring import build_seo_report

    report = build_seo_report(page_data, target_keyword="sourdough bread")
    # report is a plain dict — ready to json.dumps() or save to the DB
"""

from datetime import datetime, timezone as dt_timezone

from .checks import (
    check_title, check_meta_description, check_heading_structure,
    check_image_alt_text, check_internal_links, check_canonical_url,
    check_robots_meta, check_open_graph, check_twitter_card, check_structured_data,
)
from .keyword_analysis import analyze_keywords
from .content_quality import analyze_content_quality
from .link_analysis import analyze_links
from .mobile_security import analyze_mobile_friendliness, analyze_security


# ---------------------------------------------------------------------------
# Category weights: how much each of the 3 top-level categories contributes
# to the final 0-100 score. These sum to 100 and can be tuned later without
# touching any check logic — they only live here.
# ---------------------------------------------------------------------------
CATEGORY_WEIGHTS = {
    "technical_seo": 40,
    "content_seo": 40,
    "performance": 20,
}


def _category_check(check_name, category, severity, weight, message,
                     affected_element=None, recommendation=None):
    """Small local builder so extra checks (mobile, security, performance)
    match the same shape as the existing scraper.checks results."""
    return {
        "check_name": check_name,
        "category": category,
        "severity": severity,
        "passed": severity == "pass",
        "weight": weight,
        "message": message,
        "affected_element": affected_element,
        "recommendation": recommendation,
        "skipped": False,
    }


# ---------------------------------------------------------------------------
# Additional checks that didn't fit scraper/checks.py because they consume
# the *results* of the new analysis modules, not just raw page_data.
# ---------------------------------------------------------------------------

def check_word_count(content_result: dict) -> dict:
    word_count = content_result["word_count"]

    if word_count < 300:
        return _category_check("word_count", "content_seo", "fail", 8,
                                f"Page has only {word_count} words — thin content is unlikely to rank well.",
                                recommendation="Aim for at least 300-600 words of substantive content for most page types.")
    if word_count < 600:
        return _category_check("word_count", "content_seo", "warning", 5,
                                f"Page has {word_count} words — on the shorter side.",
                                recommendation="Consider expanding content to 600+ words if this is a primary landing/blog page.")

    return _category_check("word_count", "content_seo", "pass", 8, f"Good content length ({word_count} words).")


def check_readability(content_result: dict) -> dict:
    score = content_result["readability_score"]
    label = content_result["readability_label"]

    if score < 30:
        return _category_check("readability", "content_seo", "warning", 5,
                                f"Content is difficult to read (Flesch score: {score} — {label}).",
                                recommendation="Shorten sentences and use simpler words to improve readability for a general audience.")

    return _category_check("readability", "content_seo", "pass", 5,
                            f"Readability is good (Flesch score: {score} — {label}).")


def check_keyword_density(keyword_result: dict) -> dict:
    target = keyword_result.get("target_keyword_analysis")

    if not target:
        return _category_check("keyword_density", "content_seo", "pass", 0,
                                "No target keyword provided — skipped.")

    density = target["density_in_body"]
    in_all_three = target["in_title"] and target["in_h1"] and target["in_meta_description"]

    if target["occurrences_in_body"] == 0:
        return _category_check("keyword_density", "content_seo", "fail", 8,
                                f'Target keyword "{target["keyword"]}" does not appear in the page content at all.',
                                recommendation="Use the target keyword naturally within the body content, not just in metadata.")

    if density > 3.0:
        return _category_check("keyword_density", "content_seo", "warning", 4,
                                f'Keyword density is {density}% — may look like keyword stuffing to search engines.',
                                recommendation="Reduce keyword repetition; aim for natural density around 0.5-2.5%.")

    if not in_all_three:
        return _category_check("keyword_density", "content_seo", "warning", 5,
                                f'Keyword density is healthy ({density}%), but the keyword is missing from some key locations.',
                                recommendation="Ensure the target keyword appears in the title, H1, and meta description.")

    return _category_check("keyword_density", "content_seo", "pass", 8,
                            f'Healthy keyword density ({density}%) and present in all key locations.')


def check_broken_links_status(link_result: dict) -> dict:
    broken = link_result["broken_links"]
    checked = link_result["links_checked_for_broken"]

    if not broken:
        return _category_check("broken_links", "technical_seo", "pass", 8,
                                f"No broken links found (checked {checked} link(s)).")

    severity = "fail" if len(broken) > 2 else "warning"
    weight = 8 if severity == "fail" else 5
    example = broken[0]

    return _category_check("broken_links", "technical_seo", severity, weight,
                            f"{len(broken)} of {checked} checked link(s) are broken.",
                            affected_element=f'{example["url"]} ({example.get("status_code") or example.get("error")})',
                            recommendation="Fix or remove broken links — they harm both user experience and crawl efficiency.")


def check_anchor_text_quality(link_result: dict) -> dict:
    issues = link_result["anchor_text_issues"]

    if not issues:
        return _category_check("anchor_text_quality", "technical_seo", "pass", 3,
                                "No generic or low-quality anchor text detected.")

    severity = "warning"
    weight = 3
    return _category_check("anchor_text_quality", "technical_seo", severity, weight,
                            f"{len(issues)} link(s) use non-descriptive anchor text (e.g. 'click here', raw URLs, or empty text).",
                            recommendation="Use descriptive anchor text that tells users and search engines what the linked page is about.")


def check_mobile_friendly(mobile_result: dict) -> dict:
    if not mobile_result["has_viewport_meta"]:
        return _category_check("mobile_friendliness", "technical_seo", "fail", 8,
                                "No viewport meta tag found.",
                                affected_element='<meta name="viewport">',
                                recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1"> for proper mobile rendering.')

    if not mobile_result["viewport_configured_correctly"]:
        return _category_check("mobile_friendliness", "technical_seo", "warning", 5,
                                "Viewport meta tag is present but not configured for responsive design.",
                                affected_element=f'<meta name="viewport" content="{mobile_result["viewport_content"]}">',
                                recommendation='Update the viewport content to include "width=device-width, initial-scale=1".')

    if mobile_result.get("horizontal_scroll_on_mobile"):
        return _category_check("mobile_friendliness", "technical_seo", "warning", 5,
                                "Page content overflows horizontally at mobile screen widths.",
                                recommendation="Check for fixed-width elements (images, tables) that don't scale down on small screens.")

    return _category_check("mobile_friendliness", "technical_seo", "pass", 8, "Page is configured for responsive/mobile viewing.")


def check_https(security_result: dict) -> dict:
    if not security_result["is_https"]:
        return _category_check("https", "technical_seo", "fail", 8,
                                "Page is not served over HTTPS.",
                                recommendation="Migrate to HTTPS — it's a confirmed Google ranking signal and required for user trust.")

    if security_result["mixed_content_found"]:
        count = len(security_result["mixed_content_resources"])
        return _category_check("https", "technical_seo", "warning", 4,
                                f"Page is HTTPS but loads {count} resource(s) over insecure HTTP (mixed content).",
                                affected_element=security_result["mixed_content_resources"][0],
                                recommendation="Update all resource URLs (images, scripts, stylesheets) to use HTTPS.")

    return _category_check("https", "technical_seo", "pass", 8, "Page is served securely over HTTPS with no mixed content.")


def check_page_load_time(page_data: dict) -> dict:
    load_time_ms = page_data.get("load_time_ms")

    if load_time_ms is None:
        return _category_check("page_load_time", "performance", "pass", 0,
                                "Load time could not be measured.", recommendation=None)

    if load_time_ms > 4000:
        return _category_check("page_load_time", "performance", "fail", 10,
                                f"Page took {load_time_ms}ms to fully load — slow.",
                                recommendation="Optimize images, reduce render-blocking resources, and enable caching/compression.")
    if load_time_ms > 2500:
        return _category_check("page_load_time", "performance", "warning", 6,
                                f"Page took {load_time_ms}ms to load — could be faster.",
                                recommendation="Consider optimizing large assets to bring load time under 2.5s.")

    return _category_check("page_load_time", "performance", "pass", 10, f"Good load time ({load_time_ms}ms).")


def check_dom_content_loaded(page_data: dict) -> dict:
    dcl_ms = page_data.get("dom_content_loaded_ms")

    if dcl_ms is None:
        return _category_check("dom_content_loaded", "performance", "pass", 0,
                                "DOMContentLoaded time could not be measured.")

    if dcl_ms > 2000:
        return _category_check("dom_content_loaded", "performance", "warning", 5,
                                f"DOMContentLoaded fired at {dcl_ms}ms — page structure takes a while to become interactive.",
                                recommendation="Reduce blocking JavaScript/CSS in the <head> to speed up initial rendering.")

    return _category_check("dom_content_loaded", "performance", "pass", 5, f"Good DOMContentLoaded time ({dcl_ms}ms).")


def check_page_size(page_data: dict) -> dict:
    size_bytes = page_data.get("page_size_bytes")

    if size_bytes is None:
        return _category_check("page_size", "performance", "pass", 0, "Page size could not be measured.")

    size_kb = round(size_bytes / 1024, 1)

    if size_kb > 3000:
        return _category_check("page_size", "performance", "fail", 5,
                                f"Total page size is large ({size_kb} KB).",
                                recommendation="Compress images, minify CSS/JS, and lazy-load below-the-fold resources.")
    if size_kb > 1500:
        return _category_check("page_size", "performance", "warning", 3,
                                f"Page size is moderate ({size_kb} KB).",
                                recommendation="Consider further compressing images and assets.")

    return _category_check("page_size", "performance", "pass", 5, f"Good page size ({size_kb} KB).")


# ---------------------------------------------------------------------------
# Category assignment for the existing scraper.checks functions — these
# were written before the 3-category system existed, so we map them here
# rather than editing every function signature.
# ---------------------------------------------------------------------------
EXISTING_CHECK_CATEGORY_OVERRIDE = {
    "title_tag": "content_seo",
    "meta_description": "content_seo",
    "heading_structure": "content_seo",
    "image_alt_text": "technical_seo",
    "internal_links": "technical_seo",
    "canonical_url": "technical_seo",
    "robots_meta": "technical_seo",
    "open_graph": "technical_seo",
    "twitter_card": "technical_seo",
    "structured_data": "technical_seo",
}


def _apply_category_override(check_result: dict) -> dict:
    override = EXISTING_CHECK_CATEGORY_OVERRIDE.get(check_result["check_name"])
    if override:
        check_result = {**check_result, "category": override}
    return check_result


def calculate_category_scores(all_checks: list) -> dict:
    """
    Groups checks by category (technical_seo / content_seo / performance),
    computes each category's internal score (0-100 based on weight earned
    vs weight possible within that category), then combines them into one
    overall score using CATEGORY_WEIGHTS.
    """
    categories = {"technical_seo": [], "content_seo": [], "performance": []}

    for check in all_checks:
        cat = check.get("category")
        if cat in categories and not check.get("skipped"):
            categories[cat].append(check)

    category_scores = {}
    for cat_name, cat_checks in categories.items():
        total_weight = sum(c["weight"] for c in cat_checks)
        earned_weight = sum(c["weight"] for c in cat_checks if c["severity"] == "pass")
        cat_score = round((earned_weight / total_weight) * 100) if total_weight > 0 else 100
        category_scores[cat_name] = {
            "score": cat_score,
            "checks_passed": sum(1 for c in cat_checks if c["severity"] == "pass"),
            "checks_total": len(cat_checks),
        }

    overall_score = round(
        sum(
            category_scores[cat]["score"] * (CATEGORY_WEIGHTS[cat] / 100)
            for cat in CATEGORY_WEIGHTS
        )
    )

    return {"overall_score": overall_score, "category_scores": category_scores}


def build_seo_report(page_data: dict, target_keyword: str = None,
                      should_check_broken_links: bool = True, max_links_to_check: int = 20) -> dict:
    """
    THE single entry point. Call this from your Django background task.

    Args:
        page_data: dict returned by scraper.playwright_scraper.scrape_page()
        target_keyword: optional keyword to analyze
        check_broken_links: whether to make live HTTP requests to check link status
                             (set False for a faster, network-light audit)
        max_links_to_check: cap on how many links get checked for broken status

    Returns:
        A single structured dict — the full audit report, ready to be
        JSON-serialized and saved to the database or returned via API.
    """
    # Run the analysis modules
    keyword_result = analyze_keywords(page_data, target_keyword)
    content_result = analyze_content_quality(page_data)
    link_result = analyze_links(page_data, max_links_to_check=max_links_to_check, check_broken=should_check_broken_links)
    mobile_result = analyze_mobile_friendliness(page_data)
    security_result = analyze_security(page_data)

    # Existing on-page/technical checks (category overridden to fit the 3-bucket system)
    existing_checks = [
        _apply_category_override(check_title(page_data)),
        _apply_category_override(check_meta_description(page_data)),
        _apply_category_override(check_heading_structure(page_data)),
        _apply_category_override(check_image_alt_text(page_data)),
        _apply_category_override(check_internal_links(page_data)),
        _apply_category_override(check_canonical_url(page_data)),
        _apply_category_override(check_robots_meta(page_data)),
        _apply_category_override(check_open_graph(page_data)),
        _apply_category_override(check_twitter_card(page_data)),
        _apply_category_override(check_structured_data(page_data)),
    ]

    # New checks that depend on the analysis module results
    new_checks = [
        check_word_count(content_result),
        check_readability(content_result),
        check_keyword_density(keyword_result),
        check_broken_links_status(link_result),
        check_anchor_text_quality(link_result),
        check_mobile_friendly(mobile_result),
        check_https(security_result),
        check_page_load_time(page_data),
        check_dom_content_loaded(page_data),
        check_page_size(page_data),
    ]

    all_checks = existing_checks + new_checks
    scoring = calculate_category_scores(all_checks)

    suggestions = [
        {"check_name": c["check_name"], "severity": c["severity"], "message": c["message"],
         "recommendation": c["recommendation"]}
        for c in all_checks if c["severity"] != "pass" and not c.get("skipped")
    ]

    return {
        "url": page_data.get("url"),
        "final_url": page_data.get("final_url"),
        "scanned_at": datetime.now(dt_timezone.utc).isoformat(),
        "overall_score": scoring["overall_score"],
        "category_scores": scoring["category_scores"],
        "checks": all_checks,
        "suggestions": suggestions,
        "keyword_analysis": keyword_result,
        "content_quality": content_result,
        "link_analysis": link_result,
        "mobile_friendliness": mobile_result,
        "security": security_result,
        "performance": {
            "load_time_ms": page_data.get("load_time_ms"),
            "dom_content_loaded_ms": page_data.get("dom_content_loaded_ms"),
            "page_size_bytes": page_data.get("page_size_bytes"),
        },
    }