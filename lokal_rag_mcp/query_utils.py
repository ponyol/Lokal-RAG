"""
Query Utilities for MCP Server

Pure functions for query processing and expansion.
These utilities improve search quality, especially for date-based queries.
"""

import re
from typing import Literal, Optional


def detect_query_language(query: str) -> Literal["ru", "en", "mixed"]:
    """
    Detect the primary language of a search query.

    Uses simple heuristic based on character sets:
    - Cyrillic characters → Russian
    - Latin characters → English
    - Mix of both → Mixed

    Args:
        query: The search query text

    Returns:
        "ru" if primarily Russian (Cyrillic)
        "en" if primarily English (Latin)
        "mixed" if contains significant amounts of both

    Example:
        >>> detect_query_language("документы за октябрь")
        'ru'
        >>> detect_query_language("documents in october")
        'en'
        >>> detect_query_language("документы machine learning")
        'mixed'
        >>> detect_query_language("октябрь 2024")
        'ru'
    """
    # Count Cyrillic characters (Russian alphabet)
    cyrillic_count = len(re.findall(r'[а-яёА-ЯЁ]', query))

    # Count Latin characters (English alphabet)
    latin_count = len(re.findall(r'[a-zA-Z]', query))

    # If no alphabetic characters, return "en" as default
    if cyrillic_count == 0 and latin_count == 0:
        return "en"

    # Calculate percentages
    total_alpha = cyrillic_count + latin_count
    cyrillic_percent = cyrillic_count / total_alpha if total_alpha > 0 else 0
    latin_percent = latin_count / total_alpha if total_alpha > 0 else 0

    # If more than 20% of characters are from the other alphabet, it's mixed
    if cyrillic_percent > 0.2 and latin_percent > 0.2:
        return "mixed"

    # Primary language is whichever has more characters
    if cyrillic_count > latin_count:
        return "ru"
    else:
        return "en"


def validate_query_language(
    query: str,
    expected_language: Literal["ru", "en"],
) -> Optional[dict]:
    """
    Validate that query language matches expected language.

    Returns None if valid, or an error dict if language mismatch.

    Args:
        query: The search query
        expected_language: Expected language ("ru" or "en")

    Returns:
        None if query language matches expected_language
        Error dict with details if language mismatch

    Example:
        >>> validate_query_language("документы за октябрь", "ru")
        None  # Valid

        >>> error = validate_query_language("documents in october", "ru")
        >>> error["error"]
        'language_mismatch'
        >>> error["detected_language"]
        'en'

        >>> validate_query_language("память Claude команды", "ru")
        None  # Valid - mixed, but majority is Russian

        >>> error = validate_query_language("память Claude команды", "en")
        >>> error["error"]
        'language_mismatch'
        >>> error["detected_language"]
        'mixed_ru'  # Mixed but majority Russian
    """
    detected = detect_query_language(query)

    # Determine the actual language to validate against
    if detected == "mixed":
        # For mixed queries, check majority language
        cyrillic_count = len(re.findall(r'[а-яёА-ЯЁ]', query))
        latin_count = len(re.findall(r'[a-zA-Z]', query))

        majority_language = "ru" if cyrillic_count > latin_count else "en"

        # If majority matches expected, allow it
        if majority_language == expected_language:
            return None  # Valid mixed query

        # Otherwise, it's a mismatch
        detected_label = f"mixed_{majority_language}"
    else:
        # Pure language - must match exactly
        if detected == expected_language:
            return None  # Valid

        detected_label = detected

    # If we got here, there's a language mismatch
    # Create helpful error message
    if expected_language == "ru":
        suggestion = (
            "Пожалуйста, переведите запрос на русский язык. "
            "База знаний содержит только русские документы."
        )
        suggestion_en = (
            "Please translate your query to Russian. "
            "The knowledge base contains only Russian documents."
        )
    else:  # expected_language == "en"
        suggestion = (
            "Please translate your query to English. "
            "The knowledge base contains only English documents."
        )
        suggestion_en = suggestion

    return {
        "error": "language_mismatch",
        "detected_language": detected_label,
        "expected_language": expected_language,
        "original_query": query,
        "suggestion_ru": suggestion if expected_language == "ru" else None,
        "suggestion_en": suggestion_en,
    }


def fn_expand_query_with_dates(query: str) -> str:
    """
    Expand query with date variations to improve semantic search for date-based queries.

    This function detects mentions of months/dates in the query and adds
    alternative forms (e.g., nominative and genitive cases in Russian) to
    improve vector search recall for date-related questions.

    Why this matters:
    - Documents contain dates like "8 октября 2025", "14 октября 2025"
    - User queries use nominative case: "документы за октябрь"
    - BM25 requires exact token matches
    - Expanding "октябрь" → "октябрь октября 1 октября 2 октября дат октября"
    - Now BM25 can match both "октябрь" and "октября" forms

    Args:
        query: The original user query

    Returns:
        str: The expanded query with date variations

    Example:
        >>> fn_expand_query_with_dates("документы за август")
        "документы за август августа 1 августа 2 августа дат августа"
        >>> fn_expand_query_with_dates("какие есть документы за июль и август?")
        "какие есть документы за июль июля 1 июля 2 июля дат июля и август августа 1 августа 2 августа дат августа?"
        >>> fn_expand_query_with_dates("files from October")
        "files from October oct 1 October 2 October"
    """
    # Russian month mappings: nominative → genitive case
    russian_months = {
        "январь": "января",
        "февраль": "февраля",
        "март": "марта",
        "апрель": "апреля",
        "май": "мая",
        "июнь": "июня",
        "июль": "июля",
        "август": "августа",
        "сентябрь": "сентября",
        "октябрь": "октября",
        "ноябрь": "ноября",
        "декабрь": "декабря",
    }

    # English month mappings (add abbreviated forms)
    english_months = {
        "january": "jan",
        "february": "feb",
        "march": "mar",
        "april": "apr",
        "may": "may",
        "june": "jun",
        "july": "jul",
        "august": "aug",
        "september": "sep",
        "october": "oct",
        "november": "nov",
        "december": "dec",
    }

    expanded_query = query

    # Expand Russian months with common date patterns
    for nominative, genitive in russian_months.items():
        # Add genitive case after nominative (e.g., "август" → "август августа")
        if nominative in query.lower():
            # Use word boundary to avoid partial matches
            pattern = r'\b' + re.escape(nominative) + r'\b'
            # Add: genitive form + common date patterns with numbers
            replacement = f"{nominative} {genitive} 1 {genitive} 2 {genitive} дат {genitive}"
            expanded_query = re.sub(pattern, replacement, expanded_query, flags=re.IGNORECASE)

    # Expand English months
    for full_month, abbrev in english_months.items():
        if full_month in query.lower():
            pattern = r'\b' + re.escape(full_month) + r'\b'
            replacement = f"{full_month} {abbrev} 1 {full_month} 2 {full_month}"
            expanded_query = re.sub(pattern, replacement, expanded_query, flags=re.IGNORECASE)

    return expanded_query
