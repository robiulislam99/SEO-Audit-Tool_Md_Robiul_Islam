# scraper/keyword_analysis.py

"""
Keyword analysis: extracts the most frequent meaningful words on a page,
calculates keyword density, and checks whether a target keyword (if given)
appears in the key SEO locations (title, H1, meta description).

Usage:
    from scraper.keyword_analysis import analyze_keywords

    result = analyze_keywords(page_data, target_keyword="sourdough bread")
"""

from collections import Counter
from .text_utils import tokenize_words, STOPWORDS


def extract_top_keywords(body_text: str, top_n: int = 10) -> list:
    """
    Returns the top N most frequent non-stopword words in the page's
    visible text, along with their count and density (% of total words).

    Returns:
        [{"word": str, "count": int, "density": float}, ...]
        sorted by count descending.
    """
    words = tokenize_words(body_text)
    meaningful_words = [w for w in words if w not in STOPWORDS and len(w) > 2]

    total_word_count = len(words)  # density is based on ALL words, not just filtered ones
    if total_word_count == 0:
        return []

    counts = Counter(meaningful_words)
    top_words = counts.most_common(top_n)

    return [
        {
            "word": word,
            "count": count,
            "density": round((count / total_word_count) * 100, 2),
        }
        for word, count in top_words
    ]


def check_keyword_presence(page_data: dict, target_keyword: str) -> dict:
    """
    Checks whether target_keyword appears in title, H1, and meta description.
    Returns a breakdown dict rather than a single pass/fail, so the caller
    can build whatever check/message logic it needs from the raw facts.
    """
    keyword = target_keyword.lower().strip()
    title = (page_data.get("title") or "").lower()
    meta_desc = (page_data.get("meta_description") or "").lower()
    h1_text = " ".join(page_data.get("h1_tags", [])).lower()
    body_text = (page_data.get("body_text") or "").lower()

    body_words = tokenize_words(body_text)
    keyword_words = tokenize_words(keyword)
    # Count occurrences of the keyword phrase within the body (simple substring count on joined words)
    body_occurrences = body_text.count(keyword) if keyword else 0
    body_density = round((body_occurrences / len(body_words)) * 100, 2) if body_words and keyword else 0.0

    return {
        "keyword": target_keyword,
        "in_title": keyword in title,
        "in_h1": keyword in h1_text,
        "in_meta_description": keyword in meta_desc,
        "occurrences_in_body": body_occurrences,
        "density_in_body": body_density,
    }


def analyze_keywords(page_data: dict, target_keyword: str = None) -> dict:
    """
    Main entry point for keyword analysis.

    Returns:
        {
            "top_keywords": [{"word", "count", "density"}, ...],
            "target_keyword_analysis": dict | None,
        }
    """
    body_text = page_data.get("body_text", "")

    result = {
        "top_keywords": extract_top_keywords(body_text, top_n=10),
        "target_keyword_analysis": None,
    }

    if target_keyword:
        result["target_keyword_analysis"] = check_keyword_presence(page_data, target_keyword)

    return result