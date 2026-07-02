# scraper/content_quality.py

"""
Content quality analysis: word count, paragraph count, average sentence
length, and a basic readability score (Flesch Reading Ease approximation).

Usage:
    from scraper.content_quality import analyze_content_quality

    result = analyze_content_quality(page_data)
"""

from .text_utils import tokenize_words, split_sentences, count_syllables, clean_text


def calculate_flesch_reading_ease(word_count: int, sentence_count: int, syllable_count: int) -> float:
    """
    Standard Flesch Reading Ease formula:
        206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)

    Higher score = easier to read. Typical bands:
        90-100: Very easy (5th grade)
        60-70:  Standard (8th-9th grade)
        30-50:  Difficult (college level)
        0-30:   Very difficult (graduate level)
    """
    if word_count == 0 or sentence_count == 0:
        return 0.0

    score = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
    return round(max(0.0, min(100.0, score)), 1)


def readability_label(score: float) -> str:
    """Converts a numeric Flesch score into a plain-English label."""
    if score >= 80:
        return "Very easy to read"
    elif score >= 60:
        return "Easy to read"
    elif score >= 50:
        return "Fairly difficult to read"
    elif score >= 30:
        return "Difficult to read"
    else:
        return "Very difficult to read"


def analyze_content_quality(page_data: dict) -> dict:
    """
    Main entry point for content quality analysis.

    Expects page_data to include:
        "body_text": str  — all visible text content on the page
        "paragraphs": list[str]  — text of each <p> element

    Returns:
        {
            "word_count": int,
            "paragraph_count": int,
            "sentence_count": int,
            "avg_sentence_length": float,   # words per sentence
            "readability_score": float,     # Flesch Reading Ease, 0-100
            "readability_label": str,
        }
    """
    body_text = clean_text(page_data.get("body_text", ""))
    paragraphs = page_data.get("paragraphs", [])

    words = tokenize_words(body_text)
    sentences = split_sentences(body_text)

    word_count = len(words)
    sentence_count = len(sentences)
    paragraph_count = len([p for p in paragraphs if clean_text(p)])

    avg_sentence_length = round(word_count / sentence_count, 1) if sentence_count > 0 else 0.0

    syllable_count = sum(count_syllables(w) for w in words)
    readability_score = calculate_flesch_reading_ease(word_count, sentence_count, syllable_count)

    return {
        "word_count": word_count,
        "paragraph_count": paragraph_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": avg_sentence_length,
        "readability_score": readability_score,
        "readability_label": readability_label(readability_score),
    }