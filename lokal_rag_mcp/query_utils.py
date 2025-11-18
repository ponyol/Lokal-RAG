"""
Query Utilities for MCP Server

Pure functions for query processing and expansion.
These utilities improve search quality, especially for date-based queries.
"""

import re
from typing import Optional


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
