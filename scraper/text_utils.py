# scraper/text_utils.py

"""
Shared, dependency-free text processing helpers.

Deliberately avoids heavy NLP libraries (nltk, spacy) to keep the project
beginner-friendly and fast to install — everything here is plain Python
regex and basic heuristics, which is sufficient for SEO-level analysis
(we're not doing linguistics research, just word/sentence counting).
"""

import re

# A small, common English stopword list. Not exhaustive, but covers the
# words that would otherwise dominate every "top keywords" list uselessly
# (e.g. "the", "and", "is") without pulling in an external dependency.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "once", "here", "there", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "s", "t", "can",
    "will", "just", "don", "should", "now", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "having", "do", "does",
    "did", "doing", "of", "it", "its", "this", "that", "these", "those",
    "i", "you", "he", "she", "we", "they", "them", "their", "our", "your",
    "his", "her", "as", "which", "who", "whom", "what", "how", "why",
    "also", "us", "our", "we're", "you're", "it's",
}


def clean_text(raw_text: str) -> str:
    """Collapses whitespace and strips leading/trailing space from raw extracted text."""
    if not raw_text:
        return ""
    return re.sub(r"\s+", " ", raw_text).strip()


def tokenize_words(text: str) -> list:
    """
    Splits text into lowercase words, stripping punctuation.
    Keeps hyphenated words together (e.g. "user-friendly" stays as one token)
    since splitting them would break meaningful compound SEO terms.
    """
    if not text:
        return []
    text = text.lower()
    # Match sequences of letters/numbers, allowing internal hyphens/apostrophes
    words = re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", text)
    return words


def split_sentences(text: str) -> list:
    """
    Splits text into sentences using basic punctuation boundaries.
    Not perfect (won't handle "Mr. Smith" correctly, for example), but
    good enough for an average-sentence-length estimate at SEO-audit scale.
    """
    if not text:
        return []
    # Split on . ! ? followed by whitespace or end of string
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw_sentences if s.strip()]


def count_syllables(word: str) -> int:
    """
    Rough syllable estimator based on vowel-group counting.
    This is the standard lightweight heuristic used in most simple
    readability tools (not linguistically perfect, but consistent
    and good enough to approximate Flesch Reading Ease).
    """
    word = word.lower()
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0

    vowel_groups = re.findall(r"[aeiouy]+", word)
    syllables = len(vowel_groups)

    # Silent trailing 'e' usually doesn't add a syllable (e.g. "make")
    if word.endswith("e") and syllables > 1:
        syllables -= 1

    return max(syllables, 1)  # every word has at least 1 syllable