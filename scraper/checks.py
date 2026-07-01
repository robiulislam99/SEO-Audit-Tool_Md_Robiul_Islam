# scraper/checks.py

"""
SEO analysis engine for the SEO Audit Tool.

Takes the dictionary produced by scraper.playwright_scraper.scrape_page()
and runs a series of independent checks against it. Each check returns a
standardized result. The main entry point, analyze_seo(), combines them
into an overall score (0-100) and a list of improvement suggestions.

Usage:
    from scraper.playwright_scraper import scrape_page
    from scraper.checks import analyze_seo

    page_data = scrape_page("https://example.com")
    analysis = analyze_seo(page_data, target_keyword="seo audit tool")
    print(analysis["score"])
    print(analysis["suggestions"])
"""

import re
from collections import Counter


# ---------------------------------------------------------
# Individual check functions
# Each returns: {"check_name", "category", "passed", "weight", "message"}
# ---------------------------------------------------------

def check_title(page_data: dict) -> dict:
    title = (page_data.get("title") or "").strip()
    length = len(title)

    if not title:
        return _result("title_tag", "on_page", False, 10,
                        "Missing <title> tag — every page needs one.")

    if length < 30:
        return _result("title_tag", "on_page", False, 10,
                        f"Title is too short ({length} chars). Aim for 50-60 characters.")

    if length > 60:
        return _result("title_tag", "on_page", False, 10,
                        f"Title is too long ({length} chars) and may be truncated in search results. Aim for 50-60 characters.")

    return _result("title_tag", "on_page", True, 10,
                    f"Title length is good ({length} chars).")


def check_meta_description(page_data: dict) -> dict:
    desc = (page_data.get("meta_description") or "").strip()
    length = len(desc)

    if not desc:
        return _result("meta_description", "on_page", False, 10,
                        "Missing meta description — this hurts click-through rate from search results.")

    if length < 120:
        return _result("meta_description", "on_page", False, 8,
                        f"Meta description is short ({length} chars). Aim for 150-160 characters.")

    if length > 160:
        return _result("meta_description", "on_page", False, 8,
                        f"Meta description is too long ({length} chars) and may be truncated. Aim for 150-160 characters.")

    return _result("meta_description", "on_page", True, 10,
                    f"Meta description length is good ({length} chars).")


def check_heading_structure(page_data: dict) -> dict:
    h1_tags = page_data.get("h1_tags", [])
    h2_tags = page_data.get("h2_tags", [])

    if len(h1_tags) == 0:
        return _result("heading_structure", "on_page", False, 10,
                        "No H1 tag found. Every page should have exactly one H1.")

    if len(h1_tags) > 1:
        return _result("heading_structure", "on_page", False, 8,
                        f"Multiple H1 tags found ({len(h1_tags)}). Use only one H1 per page.")

    if len(h2_tags) == 0:
        return _result("heading_structure", "on_page", False, 5,
                        "No H2 tags found. Subheadings help structure content for readers and search engines.")

    return _result("heading_structure", "on_page", True, 10,
                    f"Good heading structure: 1 H1, {len(h2_tags)} H2(s).")


def check_image_alt_text(page_data: dict) -> dict:
    images = page_data.get("images", [])

    if not images:
        return _result("image_alt_text", "on_page", True, 5,
                        "No images found on this page.")

    missing_alt = [img for img in images if not img.get("alt") or not img["alt"].strip()]
    missing_count = len(missing_alt)
    total_count = len(images)

    if missing_count == 0:
        return _result("image_alt_text", "on_page", True, 10,
                        f"All {total_count} image(s) have alt text.")

    ratio_missing = missing_count / total_count

    if ratio_missing > 0.5:
        return _result("image_alt_text", "on_page", False, 10,
                        f"{missing_count} of {total_count} images are missing alt text. This hurts accessibility and image SEO.")

    return _result("image_alt_text", "on_page", False, 6,
                    f"{missing_count} of {total_count} images are missing alt text.")


def check_keyword_usage(page_data: dict, target_keyword: str = None) -> dict:
    """
    Basic keyword usage check. If no target_keyword is given, this check
    is skipped (returns passed=True with a neutral message) rather than
    failing — you can't judge keyword usage without knowing the target.
    """
    if not target_keyword:
        return _result("keyword_usage", "on_page", True, 0,
                        "No target keyword provided — skipped keyword analysis.", skipped=True)

    keyword = target_keyword.lower().strip()
    title = (page_data.get("title") or "").lower()
    meta_desc = (page_data.get("meta_description") or "").lower()
    h1_text = " ".join(page_data.get("h1_tags", [])).lower()

    in_title = keyword in title
    in_meta = keyword in meta_desc
    in_h1 = keyword in h1_text

    hits = sum([in_title, in_meta, in_h1])

    if hits == 0:
        return _result("keyword_usage", "on_page", False, 10,
                        f'Target keyword "{target_keyword}" was not found in the title, meta description, or H1.')

    if hits == 3:
        return _result("keyword_usage", "on_page", True, 10,
                        f'Target keyword "{target_keyword}" appears in title, meta description, and H1. Well optimized.')

    missing_from = []
    if not in_title:
        missing_from.append("title")
    if not in_meta:
        missing_from.append("meta description")
    if not in_h1:
        missing_from.append("H1")

    return _result("keyword_usage", "on_page", False, 6,
                    f'Target keyword "{target_keyword}" is missing from: {", ".join(missing_from)}.')


def check_links(page_data: dict) -> dict:
    """Bonus check: flags pages with very few internal links (weak site structure)."""
    internal = page_data.get("links", {}).get("internal", [])

    if len(internal) == 0:
        return _result("internal_links", "technical", False, 5,
                        "No internal links found. Internal linking helps search engines discover your other pages.")

    if len(internal) < 3:
        return _result("internal_links", "technical", False, 3,
                        f"Only {len(internal)} internal link(s) found. Consider adding more to improve site structure.")

    return _result("internal_links", "technical", True, 5,
                    f"{len(internal)} internal links found — good site structure.")


# ---------------------------------------------------------
# Helper to standardize check results
# ---------------------------------------------------------

def _result(check_name, category, passed, weight, message, skipped=False):
    return {
        "check_name": check_name,
        "category": category,
        "passed": passed,
        "weight": weight,
        "message": message,
        "skipped": skipped,
    }


# ---------------------------------------------------------
# Main entry point
# ---------------------------------------------------------

def analyze_seo(page_data: dict, target_keyword: str = None) -> dict:
    """
    Runs all SEO checks against the scraped page data and produces
    an overall score and suggestion list.

    Args:
        page_data: dict returned by scraper.playwright_scraper.scrape_page()
        target_keyword: optional keyword to check usage of (e.g. "seo audit tool")

    Returns:
        {
            "score": int,                # 0-100
            "results": list[dict],       # one dict per check (see _result())
            "suggestions": list[str],    # messages for every failed check
        }
    """

    checks = [
        check_title(page_data),
        check_meta_description(page_data),
        check_heading_structure(page_data),
        check_image_alt_text(page_data),
        check_keyword_usage(page_data, target_keyword),
        check_links(page_data),
    ]

    # Skipped checks don't count toward score, to avoid unfairly penalizing
    # pages when the user didn't provide a target keyword.
    scored_checks = [c for c in checks if not c.get("skipped")]

    total_weight = sum(c["weight"] for c in scored_checks)
    earned_weight = sum(c["weight"] for c in scored_checks if c["passed"])

    score = round((earned_weight / total_weight) * 100) if total_weight > 0 else 0

    suggestions = [c["message"] for c in checks if not c["passed"] and not c.get("skipped")]

    return {
        "score": score,
        "results": checks,
        "suggestions": suggestions,
    }